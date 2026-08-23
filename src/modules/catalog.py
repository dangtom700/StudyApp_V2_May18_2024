"""
modules/catalog.py  --  Book catalog / structured metadata builder for StudyApp.

Purpose
-------
Produce ONE authoritative row per PDF in the reading list, joining everything the
pipeline already knows (file_info, file_token, tags_full) with the real titles
from _original_names.json and light physical metadata (page count, size, embedded
PDF metadata). Writes a `book_catalog` table into pdf_text.db and exports
catalog.csv / catalog.json for downstream / external use.

Wire-up (already done in src/main.py)
-------------------------------------
    python src/main.py --buildCatalog        # build + export
    python src/main.py --catalogStats        # print coverage without rebuilding

Design notes
------------
* Source of truth = the PDF files on disk (READING_LIST_PATH), NOT the DB, so files
  that were never text-extracted still appear (with processed=0).

* The library uses three key spaces and every consumer re-derives them by hand. This
  table is the one place they meet -- join through `hash_id`, `title_id`, `txt_name`
  instead of rebuilding `'title_' || id` at each call site:

      hash_id  == <sha256> == disk stem == file_info.file_name == _original_names key
      title_id == "title_" + file_info.id (an md5)
                  -> file_token, tags_full, comparison, item_matrix,
                     relation_distance_filtered
      txt_name == <sha256>.txt  -> pdf_chunks.file_name

* file_info.id is an md5 of the file's ABSOLUTE PATH (src/lib/updateDB.hpp), so moving
  the library or editing READING_LIST_PATH silently orphans every derived table.
  `orphan_title_id` flags rows whose title_id has no matching file_token row, and the
  build prints the total -- a nonzero count means the key chain has broken.

* The build is non-destructive: rows are upserted, rows for deleted files are removed,
  and user-owned fields live in a separate `book_user_meta` table this never touches.

* PDF probing uses PyMuPDF (already pdf_to_txt.py's extraction backend), falling back
  to poppler's pdfinfo. Results are cached in book_catalog so re-runs only probe new
  files. Set PROBE_PDFS=False to skip it entirely.
"""

import os
import re
import csv
import json
import time
import sqlite3
import subprocess
from collections import Counter

from modules.path import pdf_path, chunk_database_path, data_folder, source_data
from modules.extract_text import (
    load_name_map,
    DEFAULT_CHUNK_SIZE,
    CHUNK_OVERLAP_RATIO,
    CHUNK_UNIT,
)

CATALOG_VERSION = 2         # bump when COLS changes; triggers a table rebuild
PROBE_VERSION = 2           # bump when probe_pdf's output changes; invalidates the probe cache
CATALOG_DIR = os.path.join(data_folder, "catalog")
PROBE_PDFS = True           # set False to skip PDF probing (fast, no page_count)
PDFINFO_TIMEOUT = 8         # seconds per file, pdfinfo fallback only
OTHER_DOMAIN = 'Other / Uncategorized'

# PyMuPDF is the same backend modules/pdf_to_txt.py already uses for extraction.
# It replaces ~2,600 pdfinfo subprocess spawns and drops the poppler dependency,
# which is not installed on every machine that runs this pipeline.
try:
    import fitz
    PROBE_BACKEND = 'pymupdf'
except ImportError:
    fitz = None
    PROBE_BACKEND = 'pdfinfo'

# --- coarse domain taxonomy (title-first; falls back to topic tags) -----------
DOMAINS = [
    ('AI & Machine Learning',        r'(machine learning|artificial intelligence|deep learning|neural network|generative|\bllm\b|natural language|data mining|reinforcement learning|computer vision)'),
    ('Data & Analytics',             r'(big data|analytics|data analysis|data science|database|data lifecycle|visualization|informatics|statistical)'),
    ('Energy & Sustainability',      r'(energy|sustainab|renewable|solar|\bwind\b|green |carbon|climate|environmental|\bwaste\b|recycling|photovolta|battery|hydrogen|biofuel|power plant|nuclear)'),
    ('Healthcare & Medicine',        r'(health|medical|medicine|clinical|patient|surgery|surgical|disease|cancer|nursing|pharma|\bdrug|biomedical|anatomy|neuro|therap|diagnos)'),
    ('Biology & Life Sciences',      r'(biology|biolog|genetic|genom|\bcell\b|molecular|ecolog|systems biology|bioinformatics|microbio|organism|protein)'),
    ('Materials & Chemistry',        r'(material|chemistry|chemical|polymer|nanomaterial|nanotech|composite|corrosion|coating|catalys|crystal|graphene|alloy)'),
    ('Electrical & Electronics',     r'(vlsi|circuit|semiconductor|electronic|electrical|antenna|microwave|photonic|\bsensor|embedded|fpga|signal processing|power electronic)'),
    ('Networks, IoT & Security',     r'(network|wireless|\b5g\b|\b6g\b|communication|internet of things|\biot\b|telecom|protocol|cyber|security|blockchain|cloud comput|edge comput)'),
    ('Mechanical & Manufacturing',   r'(manufactur|mechanical|robot|machining|welding|additive|3d print|\bcnc\b|assembly|tribolog|fluid mechanic)'),
    ('Civil & Construction',         r'(construction|structural|civil eng|concrete|building|infrastructure|geotech|bridge|architectur|urban)'),
    ('Control & Automation',         r'(control system|control theory|feedback control|\bpid\b|scada|\bplc\b|automation|instrumentation|process control)'),
    ('Mathematics & Statistics',     r'(mathematic|algebra|geometr|topology|calculus|probability|theorem|numerical method|optimization|differential equation)'),
    ('Physics & Astronomy',          r'(physics|quantum|astronom|astrophys|cosmol|particle physic|\boptic|thermodynamic|electromagnet)'),
    ('Earth & Environmental Science', r'(geolog|\bearth\b|atmospher|ocean|hydrolog|\bsoil\b|mineral|seismic|water resource|meteorolog)'),
    ('Business & Management',        r'(management|business|marketing|finance|financial|economic|supply chain|entrepreneur|operations management|leadership|strategy)'),
    ('Social Sciences & Humanities', r'(education|pedagog|history|philosophy|psycholog|sociolog|political|\bculture|gender|literature|linguistic|\blaw\b|ethic|religio)'),
    ('Agriculture & Food',           r'(agricultur|\bfood\b|\bcrop|farming|livestock|nutrition|fisher|forestry|horticultur)'),
]
_DOMAIN_RES = [(name, re.compile(pat, re.I)) for name, pat in DOMAINS]

TS_RE = re.compile(r'_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}\.pdf$')

# Function words that are common in one language and rare in the others. Deliberately
# small: this only has to answer "is the pipeline's English assumption safe for this
# book?", not identify the language precisely. Everything else reports 'und'.
_LANG_MARKERS = {
    'en': {'the', 'and', 'of', 'to', 'in', 'is', 'that', 'for', 'with', 'as', 'are', 'this'},
    'es': {'el', 'la', 'de', 'que', 'y', 'en', 'los', 'del', 'las', 'por', 'con', 'una'},
    'fr': {'le', 'la', 'de', 'et', 'les', 'des', 'est', 'pour', 'dans', 'du', 'une', 'par'},
    'de': {'der', 'die', 'und', 'das', 'den', 'von', 'ist', 'mit', 'des', 'dem', 'ein', 'auf'},
    'pt': {'de', 'que', 'em', 'os', 'as', 'para', 'com', 'uma', 'dos', 'nao', 'por', 'mais'},
    'it': {'di', 'che', 'il', 'la', 'per', 'del', 'con', 'non', 'una', 'sono', 'della', 'gli'},
    'nl': {'de', 'het', 'een', 'van', 'en', 'is', 'dat', 'op', 'te', 'voor', 'met', 'zijn'},
}
_WORD_RE = re.compile(r"[a-zà-öø-ÿ]+")

# The two date formats the probes produce. PyMuPDF hands back the raw PDF string
# ("D:20260310014739+05'30'"), where the year runs straight into the month and so has
# no trailing word boundary; pdfinfo pretty-prints it ("Sat Mar 10 01:47:39 2026").
_PDF_DATE_RE = re.compile(r"^D?:?\s*(\d{4})")
_TEXT_YEAR_RE = re.compile(r"\b(1[4-9]\d{2}|20\d{2}|21\d{2})\b")


def _clean_title(name):
    name = TS_RE.sub('', name)
    return re.sub(r'\.pdf$', '', name, flags=re.I).strip()


# --- classification ----------------------------------------------------------

def _domain_scores(text):
    """
    Score every domain by how many *distinct* keywords of its pattern the text matches.

    The original implementation returned the first domain whose pattern matched at all,
    which let broad patterns sitting early in DOMAINS win every tie -- Energy &
    Sustainability took 18% of the library that way. Scoring all 18 and taking the
    highest makes the decision comparable, and the margin makes it auditable.
    """
    scores = {}
    for name, rx in _DOMAIN_RES:
        hits = {m.group(0).lower() for m in rx.finditer(text)}
        if hits:
            scores[name] = len(hits)
    return scores


def classify(title, topics):
    """
    Return (domain, source, confidence, matches).

    `source` says which evidence decided it ('title' | 'topics' | 'none'), `matches` is
    the winner's keyword count (thin evidence is visible, not hidden), and `confidence`
    is the winner's share of all keyword matches across domains -- 1.0 means nothing
    else matched, 0.5 means it barely edged out the field.
    """
    for text, source in ((title, 'title'), (' '.join(topics), 'topics')):
        if not text:
            continue

        scores = _domain_scores(text)
        if not scores:
            continue

        # Ties break alphabetically rather than by position in DOMAINS -- deliberately,
        # since position is exactly the bias this replaced. A tie shows up as a
        # confidence well below 1.0, so it stays visible instead of looking decisive.
        name, matches = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        return name, source, round(matches / sum(scores.values()), 3), matches

    return OTHER_DOMAIN, 'none', 0.0, 0


def detect_language(text, min_words=200):
    """Best-effort language of a text sample. 'und' when the evidence is thin or close."""
    words = _WORD_RE.findall(text.lower())
    if len(words) < min_words:
        return 'und'

    counts = Counter(words)
    scores = {lang: sum(counts[w] for w in markers) for lang, markers in _LANG_MARKERS.items()}
    best_lang = max(scores, key=scores.get)
    best = scores[best_lang]

    # Almost no function words at all -- a formula dump, a scanned index, a word list.
    if best / len(words) < 0.02:
        return 'und'

    runner_up = max(v for k, v in scores.items() if k != best_lang)
    return best_lang if best >= runner_up * 1.5 else 'und'


# --- physical / text-layer probes --------------------------------------------

def _text_health(hash_id, cache):
    """
    (bytes, status, language) for the raw .txt this book should have produced.

    Splits what `processed` used to conflate: a book with no chunks might never have
    been attempted ('missing') or might be a scan with no text layer at all ('empty'),
    which pdf_to_txt.py detects and then throws away. Only the second needs OCR.

    The file is opened only when its size differs from what was recorded last build.
    The text lives on the same slow volume as everything else here, and reading a
    sample from every book is what dominates an otherwise sub-second rebuild.
    """
    path = os.path.join(source_data, hash_id + '.txt')

    try:
        size = os.path.getsize(path)
    except OSError:
        return 0, 'missing', 'und'

    if size == 0:
        return 0, 'empty', 'und'

    cached = cache.get(hash_id)
    if cached and cached[0] == size:
        return size, 'ok', cached[1]

    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            sample = f.read(8192)
    except OSError:
        return size, 'ok', 'und'

    return size, 'ok', detect_language(sample)


def _year_of(value):
    """
    Year out of a PDF date string, in either backend's format.

    This is the year the *file* was produced, not the year the book was published --
    for a re-exported or downloaded PDF the two are often decades apart.
    """
    if not value:
        return ''

    text = str(value).strip()
    match = _PDF_DATE_RE.match(text) or _TEXT_YEAR_RE.search(text)
    if not match:
        return ''

    year = int(match.group(1))
    return year if 1400 <= year <= 2200 else ''


def _probe_fitz(path):
    """(pages, title, author, producer, year, needs_password) via PyMuPDF."""
    with fitz.open(path) as doc:
        meta = doc.metadata or {}
        return (doc.page_count,
                (meta.get('title') or '').strip(),
                (meta.get('author') or '').strip(),
                (meta.get('producer') or '').strip(),
                _year_of(meta.get('creationDate')),
                1 if doc.needs_pass else 0)


def _probe_pdfinfo(path):
    """Same tuple via poppler's pdfinfo, for machines without PyMuPDF."""
    out = subprocess.run(['pdfinfo', path], capture_output=True, text=True,
                         timeout=PDFINFO_TIMEOUT, errors='ignore').stdout

    fields = {}
    for line in out.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            fields[key.strip()] = value.strip()

    pages = fields.get('Pages', '')
    return (int(pages) if pages.isdigit() else '',
            fields.get('Title', ''), fields.get('Author', ''), fields.get('Producer', ''),
            _year_of(fields.get('CreationDate')),
            1 if fields.get('Encrypted', 'no').startswith('yes') else 0)


def probe_pdf(path):
    """Physical metadata for one PDF. Empty fields on any failure -- never raises."""
    try:
        return _probe_fitz(path) if fitz else _probe_pdfinfo(path)
    except Exception:
        return '', '', '', '', '', ''


# --- schema ------------------------------------------------------------------

COLS = [
    'hash_id', 'title', 'title_source',
    'domain', 'domain_source', 'domain_confidence', 'domain_matches',
    'primary_topic', 'topics',
    'processed', 'text_status', 'text_bytes', 'language',
    'page_count', 'chunk_count', 'total_tokens', 'unique_tokens', 'relational_distance',
    'download_copies', 'file_size_bytes',
    'pdf_title', 'pdf_author', 'pdf_producer', 'pdf_year', 'needs_password',
    'title_id', 'txt_name', 'orphan_title_id', 'file_path',
]

# Fields worth reusing from a previous build instead of re-probing 2,600 large PDFs.
PROBE_COLS = ['page_count', 'pdf_title', 'pdf_author', 'pdf_producer', 'pdf_year',
              'needs_password']

CATALOG_DDL = """
    CREATE TABLE IF NOT EXISTS book_catalog (
        hash_id             TEXT PRIMARY KEY,
        title               TEXT,
        title_source        TEXT,
        domain              TEXT,
        domain_source       TEXT,
        domain_confidence   REAL,
        domain_matches      INTEGER,
        primary_topic       TEXT,
        topics              TEXT,
        processed           INTEGER,
        text_status         TEXT,
        text_bytes          INTEGER,
        language            TEXT,
        page_count          INTEGER,
        chunk_count         INTEGER,
        total_tokens        INTEGER,
        unique_tokens       INTEGER,
        relational_distance REAL,
        download_copies     INTEGER,
        file_size_bytes     INTEGER,
        pdf_title           TEXT,
        pdf_author          TEXT,
        pdf_producer        TEXT,
        pdf_year            INTEGER,
        needs_password      INTEGER,
        title_id            TEXT,
        txt_name            TEXT,
        orphan_title_id     INTEGER,
        file_path           TEXT
    )"""

# Everything the builder derives lives in book_catalog and is disposable. Anything a
# human enters lives here and is never written by the build -- so a schema change can
# rebuild the catalog without destroying reading progress.
USER_META_DDL = """
    CREATE TABLE IF NOT EXISTS book_user_meta (
        hash_id     TEXT PRIMARY KEY,
        read_status TEXT,
        rating      INTEGER,
        notes       TEXT,
        updated_at  INTEGER
    )"""

META_DDL = """
    CREATE TABLE IF NOT EXISTS catalog_meta (
        key   TEXT PRIMARY KEY,
        value TEXT
    )"""


def _ensure_schema(conn):
    existing = [row[1] for row in conn.execute("PRAGMA table_info(book_catalog)")]
    if existing and existing != COLS:
        # book_catalog is 100% derived from disk + the pipeline tables, so rebuilding it
        # costs one re-probe and nothing else. book_user_meta is a separate table and is
        # deliberately left alone.
        print(f"[catalog] schema changed ({len(existing)} -> {len(COLS)} columns); "
              f"rebuilding book_catalog (book_user_meta untouched).")
        conn.execute("DROP TABLE book_catalog")

    conn.execute(CATALOG_DDL)
    conn.execute(USER_META_DDL)
    conn.execute(META_DDL)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_domain   ON book_catalog(domain)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_title    ON book_catalog(title)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_catalog_title_id ON book_catalog(title_id)")

    # The view is what consumers should select from: it carries the user's own fields
    # and spares every call site from rebuilding "'title_' || file_info.id" by hand.
    conn.execute("DROP VIEW IF EXISTS v_book")
    conn.execute("""
        CREATE VIEW v_book AS
        SELECT c.*, u.read_status, u.rating, u.notes, u.updated_at
        FROM book_catalog c
        LEFT JOIN book_user_meta u USING (hash_id)""")


def _null(value):
    """'' means "no value" throughout the builder; 0 and 0.0 are real values."""
    return None if value == '' else value


def _write_table(conn, rows):
    updates = ', '.join(f"{c}=excluded.{c}" for c in COLS if c != 'hash_id')
    conn.executemany(
        f"INSERT INTO book_catalog ({', '.join(COLS)}) "
        f"VALUES ({', '.join('?' * len(COLS))}) "
        f"ON CONFLICT(hash_id) DO UPDATE SET {updates}",
        [tuple(_null(r[c]) for c in COLS) for r in rows])

    on_disk = {r['hash_id'] for r in rows}
    gone = [(h,) for (h,) in conn.execute("SELECT hash_id FROM book_catalog")
            if h not in on_disk]
    if gone:
        conn.executemany("DELETE FROM book_catalog WHERE hash_id = ?", gone)
        print(f"[catalog] removed {len(gone)} rows for files no longer on disk.")


def _write_meta(conn, meta):
    conn.executemany("INSERT INTO catalog_meta (key, value) VALUES (?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     [(k, str(v)) for k, v in meta.items()])


def _stored_probe_version(conn):
    try:
        row = conn.execute("SELECT value FROM catalog_meta WHERE key = 'probe_version'").fetchone()
        return int(row[0]) if row else 0
    except (sqlite3.OperationalError, TypeError, ValueError):
        return 0


def _load_probe_cache(conn, stale_ok=False):
    """
    Reuse physical metadata already stored so re-runs skip the PDF probe.

    Normally returns nothing when the cached values predate the current probe logic --
    without that check a fix to the metadata parsing would never reach rows already
    cached, which is how pdf_year sat empty on every row. `stale_ok` overrides it for
    --noProbe, where the choice is between stale values and blanking the columns.
    """
    cache = {}

    stored = _stored_probe_version(conn)
    if stored != PROBE_VERSION and not stale_ok:
        print(f"[catalog] probe logic changed (v{stored} -> v{PROBE_VERSION}); "
              f"re-probing every PDF once.")
        return cache

    try:
        rows = conn.execute(f"SELECT hash_id, {', '.join(PROBE_COLS)} FROM book_catalog")
    except sqlite3.OperationalError:
        return cache      # table doesn't exist yet

    for row in rows:
        # A stored row with no page count was never probed successfully -- retry it
        # rather than caching the failure forever.
        if row[1] is None:
            continue
        cache[row[0]] = tuple('' if v is None else v for v in row[1:])

    return cache


def _load_text_cache(conn):
    """Reuse a book's detected language while its extracted text is the same size."""
    cache = {}
    try:
        rows = conn.execute("SELECT hash_id, text_bytes, language FROM book_catalog")
    except sqlite3.OperationalError:
        return cache

    for h, size, language in rows:
        if size and language:
            cache[h] = (size, language)

    return cache


# --- build -------------------------------------------------------------------

def _phase(label, since):
    """Print how long a build phase took and return the new clock."""
    now = time.time()
    print(f"[catalog] {label:<24} {now - since:>7.1f}s")
    return now


def build_catalog(export=True, probe=None):
    probe = PROBE_PDFS if probe is None else probe
    started = mark = time.time()
    os.makedirs(CATALOG_DIR, exist_ok=True)

    names = load_name_map(pdf_path)

    conn = sqlite3.connect(chunk_database_path)
    cur = conn.cursor()
    _ensure_schema(conn)

    info = {}          # sha256 -> {id, path, epoch, chunk_count}
    id2hash = {}
    for _id, fn, fp, epoch, cc in cur.execute(
            "SELECT id, file_name, file_path, epoch_time, chunk_count FROM file_info"):
        info[fn] = {'id': _id, 'path': fp, 'epoch': epoch, 'chunk_count': cc}
        id2hash['title_' + _id] = fn

    tok = {}
    for fn, tt, ut, rd in cur.execute(
            "SELECT file_name, total_tokens, unique_tokens, relational_distance FROM file_token"):
        h = id2hash.get(fn)
        if h:
            tok[h] = (tt, ut, rd)
    tokenised = {row[0] for row in cur.execute("SELECT file_name FROM file_token")}

    tags = {}
    for _id, dist, topic in cur.execute("SELECT ID, distance, topic FROM tags_full"):
        h = id2hash.get(_id)
        if h:
            tags.setdefault(h, []).append((dist, topic))
    for h in tags:
        tags[h].sort(key=lambda x: x[0])   # ascending distance = strongest tag first

    # Loaded either way: --noProbe means "don't read any PDFs", not "discard the page
    # counts we already have".
    probe_cache = _load_probe_cache(conn, stale_ok=not probe)
    text_cache = _load_text_cache(conn)
    probed = 0
    mark = _phase('read pipeline tables', mark)

    pdfs = [f for f in os.listdir(pdf_path) if f.lower().endswith('.pdf')]
    mark = _phase(f'list {len(pdfs)} PDFs', mark)

    rows = []
    for n, f in enumerate(pdfs, 1):
        # The probe and the text-layer read both touch the disk once per book, so a
        # stalled file is otherwise invisible for minutes at a time.
        if n % 250 == 0:
            print(f"[catalog]   {n}/{len(pdfs)} books ({probed} probed)", flush=True)

        h = f[:-4]
        path = os.path.join(pdf_path, f)
        try:
            size = os.path.getsize(path)
        except OSError:
            size = ''

        copies = len(names.get(h, []))
        title = _clean_title(names[h][0]) if copies else ''
        src = 'name_map' if title else ''

        if h in probe_cache:
            pages, ptitle, pauthor, pproducer, pyear, locked = probe_cache[h]
        elif probe:
            pages, ptitle, pauthor, pproducer, pyear, locked = probe_pdf(path)
            probed += 1
        else:
            pages = ptitle = pauthor = pproducer = pyear = locked = ''

        if not title and ptitle:
            title, src = ptitle.strip(), 'pdf_meta'
        if not title:
            src = 'unknown'

        topics = [t for _, t in tags.get(h, [])[:8]]
        domain, domain_source, confidence, matches = classify(title, topics)

        text_bytes, text_status, language = _text_health(h, text_cache)

        inf = info.get(h, {})
        title_id = 'title_' + inf['id'] if inf else ''
        total_tokens, unique_tokens, distance = tok.get(h, ('', '', ''))

        rows.append({
            'hash_id': h, 'title': title, 'title_source': src,
            'domain': domain, 'domain_source': domain_source,
            'domain_confidence': confidence, 'domain_matches': matches,
            'primary_topic': topics[0] if topics else '', 'topics': '; '.join(topics),
            'processed': 1 if inf else 0, 'text_status': text_status,
            'text_bytes': text_bytes, 'language': language,
            'page_count': pages, 'chunk_count': inf.get('chunk_count', ''),
            'total_tokens': total_tokens, 'unique_tokens': unique_tokens,
            'relational_distance': distance,
            'download_copies': copies, 'file_size_bytes': size,
            'pdf_title': ptitle, 'pdf_author': pauthor, 'pdf_producer': pproducer,
            'pdf_year': pyear, 'needs_password': locked,
            'title_id': title_id, 'txt_name': h + '.txt',
            'orphan_title_id': 1 if (title_id and title_id not in tokenised) else 0,
            'file_path': inf.get('path') or path.replace('\\', '/'),
        })

    rows.sort(key=lambda r: (r['domain'], (r['title'] or '~').lower()))
    mark = _phase('assemble rows', mark)

    meta = {
        'catalog_version': CATALOG_VERSION,
        'built_at': int(time.time()),
        'built_at_iso': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'book_count': len(rows),
        'chunk_size': DEFAULT_CHUNK_SIZE,
        'chunk_overlap': int(DEFAULT_CHUNK_SIZE * CHUNK_OVERLAP_RATIO),
        'chunk_unit': CHUNK_UNIT,
        'probe_backend': PROBE_BACKEND if probe else 'none',
        'reading_list_path': pdf_path,
    }
    # Only a run that actually probed may claim the current probe version -- otherwise
    # --noProbe would silently mark stale metadata as up to date.
    if probe:
        meta['probe_version'] = PROBE_VERSION

    _write_table(conn, rows)
    _write_meta(conn, meta)
    conn.commit()
    mark = _phase('write book_catalog', mark)

    if export:
        _export(rows, meta)
        mark = _phase('export csv/json', mark)

    print(f"[catalog] {len(rows)} books in {time.time() - started:.1f}s "
          f"({probed} newly probed via {meta['probe_backend']})")
    catalog_stats(conn)
    conn.close()
    return rows


def catalog_stats(conn=None):
    """Print coverage. This is the source for the numbers in docs/CATALOG_DATASET_PLAN.md."""
    owned = conn is None
    if owned:
        conn = sqlite3.connect(chunk_database_path)

    try:
        total = conn.execute("SELECT COUNT(*) FROM book_catalog").fetchone()[0]
    except sqlite3.OperationalError:
        print("[catalog] book_catalog does not exist yet -- run --buildCatalog first.")
        if owned:
            conn.close()
        return

    if not total:
        print("[catalog] book_catalog is empty.")
        if owned:
            conn.close()
        return

    def count(where, *params):
        return conn.execute(f"SELECT COUNT(*) FROM book_catalog WHERE {where}", params).fetchone()[0]

    def line(label, n):
        print(f"  {label:<20} {n:>6,} ({n / total:>5.1%})")

    print(f"\n  books                {total:>6,}")
    line("titled from name map", count("title_source = 'name_map'"))
    line("titled from PDF meta", count("title_source = 'pdf_meta'"))
    line("title unknown",        count("title_source = 'unknown'"))
    line("text extracted",       count("processed = 1"))
    line("topic tagged",         count("topics IS NOT NULL AND topics != ''"))
    line("re-downloaded",        count("download_copies > 1"))
    line("uncategorized",        count("domain = ?", OTHER_DOMAIN))
    line("non-English text",     count("language NOT IN ('en', 'und')"))

    for status, n in conn.execute(
            "SELECT text_status, COUNT(*) FROM book_catalog GROUP BY 1 ORDER BY 2 DESC"):
        line({'ok': 'text layer ok', 'empty': 'no text (needs OCR)',
              'missing': 'not yet converted'}.get(status, str(status)), n)

    orphans = count("orphan_title_id = 1")
    if orphans:
        print(f"\n  !! {orphans:,} rows have a title_id with no file_token row.\n"
              f"     file_info.id is an md5 of the file's absolute path, so this usually\n"
              f"     means the library moved. Re-run --updateDatabaseInformation.")
    else:
        print(f"  key chain intact     {'':>6} (0 orphaned title_ids)")

    if owned:
        conn.close()


def _export(rows, meta):
    with open(os.path.join(CATALOG_DIR, 'catalog.json'), 'w', encoding='utf-8') as f:
        json.dump({'meta': meta, 'books': rows}, f, indent=1, ensure_ascii=False)

    # utf-8-sig, not utf-8: titles carry accents and Excel on Windows assumes the local
    # code page without the BOM. Python's csv reader strips it transparently.
    with open(os.path.join(CATALOG_DIR, 'catalog.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)

    # The CSV cannot carry the provenance block, so it travels alongside it.
    with open(os.path.join(CATALOG_DIR, 'catalog_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=1)


if __name__ == '__main__':
    build_catalog()
