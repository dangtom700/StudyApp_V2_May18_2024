"""
modules/dedupe_pdf.py  --  content-level de-duplication for the reading list.

Purpose
-------
Catch the duplicates that sha256-of-bytes cannot: a freshly downloaded,
UNCOMPRESSED book whose copy in the library has already been through
--compressPDF.

Why the existing check misses them
----------------------------------
rename_files (modules/extract_text.py) names every PDF <sha256 of its content>.pdf
and treats a name collision as a duplicate. --compressPDF then rewrites those
files in place *without* re-hashing -- deliberately, because the stem is the
library's primary key (see modules/compress_pdf.py). The consequence is that a
compressed book's bytes no longer hash to its own filename, so re-downloading the
original produces a hash that matches nothing on disk and a second copy of the
book lands in the library.

The fingerprint
---------------
Ghostscript's pdfwrite re-encodes images and subsets fonts. It does not touch the
text layer, and --compressPDF already verifies that the page count comes out
identical. So the identity signals that survive compression are, cheapest first:

  1. sha256 of the bytes            -- exact re-download; what rename_files does
  2. the download filename          -- via _original_names.json
  3. sha256 of the normalised text  -- free on the library side: every book that
                                       has been through --pdfToText already has
                                       <stem>.txt sitting in RAW_DATA_PATH
  4. Jaccard over 5-gram shingles   -- for when font subsetting perturbs word
                                       breaks and tier 3 just misses
  5. page count + per-page MediaBox -- image-only scans, which have no text layer
                                       to compare. Reported, never acted on
                                       unless --dedupeStructural.

Tiers 1-3 are dictionary lookups. Tier 4 only considers library books whose text
length is within LENGTH_BAND of the incoming file's, and only builds the
expensive shingle sketch for that handful. Tier 5 only ever opens books that have
no text at all.

Which copy is kept
------------------
Always the one already in the library, under its existing stem. file_info.id is
an md5 of the absolute path and modules/catalog.py joins everything through the
stem, so re-keying the survivor would orphan file_token, tags_full, comparison
and item_matrix -- the same constraint that forces compression to happen in
place.

The incoming file's original name is recorded in _original_names.json *before*
the file is touched, which is what keeps catalog.py's download_copies a measured
fact rather than a guess.

--preferIncoming changes which *bytes* are kept, never which name: the incoming
file replaces the library copy at the library copy's own path. Every key stays
valid, a lossy copy is upgraded back to the original, and the size check in
compress_pdf.load_ledger sees that the file no longer matches its logged
out_bytes and re-compresses it on the next --compressPDF.

Run order
---------
    --dedupePDF  ->  --renameFile  ->  --compressPDF  ->  --pdfToText  ->  ...

Before --renameFile, because that is the only point at which "incoming" is still
distinguishable from "already in the library": incoming files still carry their
download names, library files are already <sha256>.pdf. Anything this stage lets
through is then handled by rename_files exactly as before.

Safety
------
* Nothing is deleted by default. Duplicates are moved to _duplicates/ inside the
  source folder; --dedupeDelete unlinks them instead.
* --dedupeDryRun reports every proposed action and writes nothing.
* Tier 5 matches are reported but not acted on without --dedupeStructural. Two
  scans with the same page count and the same page dimensions are usually the
  same book, and "usually" is not good enough to delete on.
* data/dedupe_log.csv records every decision with the tier and score behind it.
* data/dedupe_fingerprints.json caches the library index, keyed on each file's
  size and mtime, so a re-run costs one stat() per book.
"""

import os
import re
import sys
import csv
import json
import shutil
import hashlib
import unicodedata
import concurrent.futures as cf
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.path import pdf_path, source_data, dedupe_cache_path, dedupe_log_path
from modules.extract_text import (
    HASH_NAME_PATTERN,
    hash_file_content,
    load_name_map,
    save_name_map,
    record_original_name,
)

# --- Config -----------------------------------------------------------------
QUARANTINE_DIR = "_duplicates"

# Below this many characters of normalised text a document has no usable text
# layer -- a cover page's worth of OCR noise, or nothing at all. Comparing those
# by text hash would collide every scan in the library with every other, so they
# go to the structural tier instead.
MIN_CHARS_FOR_TEXT = 400

# Fingerprints are taken from the front of a book, not all of it. 20,000 identical
# consecutive words is not something two different books do -- and the reading list
# holds 2.4 GB of extracted text, which is several minutes of pure normalisation to
# read end to end every run.
#
# The cap counts WORDS, not characters, and that is the point: a character cap would
# land mid-word at a slightly different place on each side of a pair whose text
# differs by a few leading bytes, and the two fingerprints would then disagree over
# nothing. Word indices are stable under exactly the whitespace differences that
# normalise() is there to absorb.
FINGERPRINT_WORDS = 20_000
# How much raw text to read to find those words. Generous -- real text runs ~6
# characters per word, so this holds roughly 50,000 of them.
READ_CHARS = 300_000

# Fuzzy matching is only meaningful with enough text to shingle.
MIN_WORDS_FOR_FUZZY = 300
SHINGLE_K = 5            # words per shingle
SKETCH_SIZE = 256        # bottom-k sketch: k smallest shingle hashes
FUZZY_THRESHOLD = 0.95   # estimated Jaccard at or above this is a duplicate

# Candidate filter for the fuzzy tier. Compression preserves the text layer, so a
# genuine duplicate's character count moves by rounding at most; 2% is slack for
# a font subset that shifts a few thousand word breaks in a long book.
LENGTH_BAND = 0.02

LOG_FIELDS = ("timestamp", "action", "incoming", "incoming_bytes",
              "keeper", "keeper_bytes", "tier", "score")

# Bump when the normalisation, the cap or the sketch changes -- old cached
# fingerprints are not comparable with new ones and must be rebuilt rather than
# silently mixed.
FINGERPRINT_VERSION = 2

TIER_BYTES = "sha256"
TIER_NAME = "filename"
TIER_TEXT = "text-hash"
TIER_FUZZY = "text-fuzzy"
TIER_STRUCT = "structural"

# PyMuPDF is the extraction backend for modules/pdf_to_txt.py and the verifier for
# modules/compress_pdf.py. Here it does both jobs: text for tiers 3-4, page
# geometry for tier 5.
try:
    import fitz
    HAVE_FITZ = True
except ImportError:
    fitz = None
    HAVE_FITZ = False

try:
    from pypdf import PdfReader
    HAVE_PYPDF = True
except ImportError:
    PdfReader = None
    HAVE_PYPDF = False


# --- Text fingerprints -------------------------------------------------------

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """
    Reduce text to what survives a re-encode.

    NFKC folds the ligatures (fi, fl) that font subsetting introduces or removes,
    casefold ignores a small-caps run rendered differently, and dropping
    punctuation ignores quote glyphs that change shape when a font is re-embedded.
    What is left -- the words, in order -- is what Ghostscript genuinely preserves.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()
    text = _PUNCT.sub(" ", text)
    return _SPACE.sub(" ", text).strip()


def canonical(raw: str) -> str:
    """
    The comparable form of a document: normalised, then cut to its first
    FINGERPRINT_WORDS words. Every fingerprint in this module is taken from this,
    so both sides of a comparison are always cut at the same word.
    """
    return " ".join(normalise(raw).split()[:FINGERPRINT_WORDS])


def text_sha(normalised: str) -> str:
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def read_capped(path) -> str:
    """Enough raw text to yield FINGERPRINT_WORDS words, and no more."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(READ_CHARS)
    except OSError:
        return ""


def sketch(normalised: str) -> list:
    """
    Bottom-k sketch of the document's 5-gram shingles.

    Storing the k smallest 64-bit shingle hashes gives an unbiased Jaccard
    estimate at a fixed 256-integer cost per book, instead of holding a set of
    several hundred thousand shingles per book in memory to compare exactly.
    """
    words = normalised.split()
    if len(words) < max(SHINGLE_K, MIN_WORDS_FOR_FUZZY):
        return []

    hashes = set()
    for i in range(len(words) - SHINGLE_K + 1):
        shingle = " ".join(words[i:i + SHINGLE_K]).encode("utf-8")
        hashes.add(int.from_bytes(hashlib.blake2b(shingle, digest_size=8).digest(), "big"))

    return sorted(hashes)[:SKETCH_SIZE]


def jaccard(a: list, b: list) -> float:
    """
    Estimate the Jaccard similarity of two documents from their bottom-k sketches.

    The standard bottom-k estimator: take the k smallest hashes of the union of
    the two sketches, and count how many of those appear in both.
    """
    if not a or not b:
        return 0.0

    k = min(len(a), len(b), SKETCH_SIZE)
    set_a, set_b = set(a), set(b)
    union = sorted(set_a | set_b)[:k]
    return sum(1 for h in union if h in set_a and h in set_b) / k


# --- Structural fingerprint (books with no text layer) -----------------------

def structural_key(pdf: Path):
    """
    (key, pages) for an image-only scan, or (None, None) if it cannot be read.

    Page count is preserved exactly by compression -- compress_pdf.compress_one
    refuses to replace a file whose page count changed -- and so are the page
    dimensions. Two unrelated books sharing both a page count and an identical
    per-page size sequence is uncommon, but it is a coincidence rather than proof,
    which is why acting on this tier is opt-in.
    """
    try:
        if HAVE_FITZ:
            with fitz.open(str(pdf)) as doc:
                if doc.needs_pass:
                    return None, None
                pages = doc.page_count
                dims = [(round(p.rect.width, 1), round(p.rect.height, 1)) for p in doc]
        elif HAVE_PYPDF:
            reader = PdfReader(str(pdf))
            if reader.is_encrypted:
                return None, None
            pages = len(reader.pages)
            dims = [(round(float(p.mediabox.width), 1), round(float(p.mediabox.height), 1))
                    for p in reader.pages]
        else:
            return None, None
    except Exception:
        return None, None

    digest = hashlib.sha256(repr((pages, dims)).encode("utf-8")).hexdigest()
    return digest, pages


def extract_text_from_pdf(pdf: Path, limit: int = READ_CHARS) -> str:
    """
    The first `limit` characters of a PDF's text, or "" if it has none.

    Stops as soon as it has enough rather than walking every page: only the front
    of a book is fingerprinted, and a 1,200-page atlas costs the same as a pamphlet
    this way. The leading strip() matches what pdf_to_txt.convert_one writes to
    the .txt files, so both sides of a comparison start at the same character.
    """
    parts, size = [], 0
    try:
        if HAVE_FITZ:
            with fitz.open(str(pdf)) as doc:
                if doc.needs_pass:
                    return ""
                for i in range(doc.page_count):
                    parts.append(doc[i].get_text("text"))
                    size += len(parts[-1])
                    if size >= limit:
                        break
        elif HAVE_PYPDF:
            reader = PdfReader(str(pdf))
            if reader.is_encrypted:
                return ""
            for page in reader.pages:
                parts.append(page.extract_text() or "")
                size += len(parts[-1])
                if size >= limit:
                    break
        else:
            return ""
    except Exception:
        return ""

    return "\n".join(parts).strip()[:limit]


# --- Fingerprint cache -------------------------------------------------------

def load_cache(cache_path: str = dedupe_cache_path) -> dict:
    """
    Cached library fingerprints, or an empty cache if it is missing or stale.

    A corrupt cache is not fatal here the way a corrupt _original_names.json is:
    everything in it can be recomputed from files that still exist on disk.
    """
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] Could not read {cache_path}: {e} -- rebuilding the index.")
        return {}

    if data.get("version") != FINGERPRINT_VERSION:
        return {}
    return data.get("entries", {})


def save_cache(entries: dict, cache_path: str = dedupe_cache_path) -> None:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    tmp = cache_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": FINGERPRINT_VERSION, "entries": entries}, f)
    os.replace(tmp, cache_path)


def _stamp(path):
    """(size, mtime) used to decide whether a cached fingerprint is still valid."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return [st.st_size, round(st.st_mtime, 3)]


# --- Library index -----------------------------------------------------------

def _fingerprint_txt(job):
    """
    Worker: (stem, txt_path) -> (stem, text_sha, nchars).

    Top-level and self-contained so it can be pickled to a process pool. Reading
    and normalising 2,750 books is a few minutes of pure CPU in one process, and
    it is all in C-level regex and unicode calls that do not release the GIL --
    so processes, not threads.
    """
    stem, txt_path = job
    raw = read_capped(txt_path)
    if not raw:
        return stem, None, 0

    norm = canonical(raw)
    if len(norm) < MIN_CHARS_FOR_TEXT:
        return stem, None, 0
    return stem, text_sha(norm), len(norm)


def build_index(folder: Path, cache: dict, jobs: int = 0, quiet: bool = False) -> dict:
    """
    {stem: entry} for every <sha256>.pdf in `folder`.

    The text half is read from RAW_DATA_PATH/<stem>.txt, which --pdfToText has
    already written for every book that has been through the pipeline. That is
    what keeps indexing a 2,750-book library cheap: no PDF is opened unless it has
    no .txt at all.

    Shingle sketches are deliberately NOT built here -- see _ensure_sketch.
    """
    index, todo, fresh, probed = {}, [], 0, 0

    for name in os.listdir(folder):
        if not HASH_NAME_PATTERN.match(name):
            continue

        stem = name[:-4]
        pdf = folder / name
        txt = Path(source_data) / (stem + ".txt")

        entry = dict(cache.get(stem) or {})
        txt_stamp = _stamp(txt)
        pdf_stamp = _stamp(pdf)
        entry["size"] = pdf_stamp[0] if pdf_stamp else 0
        index[stem] = entry

        # Text side: keyed on the .txt, which compression never touches.
        if txt_stamp and entry.get("txt_stamp") == txt_stamp:
            fresh += 1
        else:
            entry.pop("text_sha", None)
            entry.pop("nchars", None)
            entry.pop("sketch", None)
            entry["txt_stamp"] = txt_stamp
            if txt_stamp and txt_stamp[0] > 0:
                todo.append((stem, str(txt)))

    if todo:
        if not quiet:
            print(f"Indexing    : reading {len(todo)} book(s) of text "
                  f"({len(index) - len(todo)} cached)...")
        for stem, sha, nchars in _run_fingerprints(todo, jobs):
            if sha:
                index[stem]["text_sha"] = sha
                index[stem]["nchars"] = nchars

    # Structural side: only for books with no usable text. Keyed on the PDF, which
    # compression DOES change, so it is recomputed after a compress run. Cheap
    # because so few books ever reach it.
    for stem, entry in index.items():
        if entry.get("text_sha"):
            entry.pop("struct", None)
            entry.pop("pdf_stamp", None)
            continue

        pdf = folder / (stem + ".pdf")
        pdf_stamp = _stamp(pdf)
        if entry.get("pdf_stamp") != pdf_stamp or "struct" not in entry:
            entry["pdf_stamp"] = pdf_stamp
            entry["struct"], entry["pages"] = structural_key(pdf)
            probed += 1

    if not quiet:
        print(f"Indexed     : {len(index)} books "
              f"({fresh} cached, {len(todo)} re-read, {probed} probed)")

    return index


def _run_fingerprints(todo: list, jobs: int = 0):
    """Fingerprint many .txt files, in parallel when there are enough to be worth it."""
    if jobs <= 0:
        jobs = max(1, (os.cpu_count() or 4) - 1)

    if jobs == 1 or len(todo) < 32:
        return [_fingerprint_txt(job) for job in todo]

    try:
        with cf.ProcessPoolExecutor(max_workers=jobs) as pool:
            return list(pool.map(_fingerprint_txt, todo, chunksize=8))
    except Exception as e:
        # A process pool can fail for reasons that have nothing to do with the
        # work (spawn restrictions, a frozen interpreter). Falling back is slower
        # but always correct.
        print(f"[WARN] Parallel indexing unavailable ({e}); falling back to one process.")
        return [_fingerprint_txt(job) for job in todo]


def _ensure_sketch(stem: str, index: dict) -> list:
    """
    Shingle sketch for one library book, built on first use and cached.

    Shingling a long book is a few hundred thousand hashes. Tiers 1-3 resolve
    almost every real duplicate without one, so paying that cost for the whole
    library up front would be paying it for nothing.
    """
    entry = index[stem]
    if entry.get("sketch") is not None:
        return entry["sketch"]

    raw = read_capped(Path(source_data) / (stem + ".txt"))
    entry["sketch"] = sketch(canonical(raw)) if raw else []
    return entry["sketch"]


# --- Incoming fingerprints ---------------------------------------------------

def fingerprint_incoming(pdf: Path) -> dict:
    """Everything needed to match one incoming file, in one pass over it."""
    fp = {"path": pdf, "name": pdf.name, "size": pdf.stat().st_size,
          "sha256": None, "text_sha": None, "nchars": 0, "norm": "",
          "struct": None, "pages": None}

    try:
        fp["sha256"] = hash_file_content(str(pdf))
    except OSError:
        pass

    # extract_text_from_pdf already cuts at READ_CHARS, the same window read_capped
    # takes from the library's .txt -- the two fingerprints must see the same text.
    norm = canonical(extract_text_from_pdf(pdf))
    if len(norm) >= MIN_CHARS_FOR_TEXT:
        fp["norm"] = norm
        fp["nchars"] = len(norm)
        fp["text_sha"] = text_sha(norm)
    else:
        # No usable text layer: a scan. Structural is the only tier left.
        fp["struct"], fp["pages"] = structural_key(pdf)

    return fp


# --- Matching ----------------------------------------------------------------

def find_match(fp: dict, index: dict, by_text: dict, by_struct: dict,
               by_name: dict, threshold: float):
    """
    (stem, tier, score) for the library book this file duplicates, or None.

    Ordered cheapest-first and returns on the first hit, so the expensive tiers
    only ever run on files the cheap ones could not resolve.
    """
    # 1. Same bytes. rename_files would catch this too; doing it here means the
    #    report accounts for every file, not just the ones it alone can find.
    if fp["sha256"] and fp["sha256"] in index:
        return fp["sha256"], TIER_BYTES, 1.0

    # 2. This exact download name is already recorded against a book.
    stem = by_name.get(fp["name"])
    if stem and stem in index:
        return stem, TIER_NAME, 1.0

    # 3. Identical text layer -- the tier that catches a compressed/uncompressed pair.
    if fp["text_sha"]:
        stem = by_text.get(fp["text_sha"])
        if stem:
            return stem, TIER_TEXT, 1.0

    # 4. Near-identical text, blocked by length so this stays a handful of
    #    comparisons rather than one per book in the library.
    if fp["nchars"] >= MIN_CHARS_FOR_TEXT and len(fp["norm"].split()) >= MIN_WORDS_FOR_FUZZY:
        mine = sketch(fp["norm"])
        if mine:
            best, best_stem = 0.0, None
            for stem, entry in index.items():
                n = entry.get("nchars")
                if not n:
                    continue
                if abs(n - fp["nchars"]) > LENGTH_BAND * max(n, fp["nchars"]):
                    continue
                score = jaccard(mine, _ensure_sketch(stem, index))
                if score > best:
                    best, best_stem = score, stem
            if best_stem and best >= threshold:
                return best_stem, TIER_FUZZY, round(best, 4)

    # 5. No text on either side: same page count, same page sizes.
    if fp["struct"]:
        stem = by_struct.get(fp["struct"])
        if stem:
            return stem, TIER_STRUCT, 1.0

    return None


def _lookups(index: dict, name_map: dict):
    """Reverse lookups for tiers 2, 3 and 5, built once per run."""
    by_text, by_struct = {}, {}
    for stem, entry in index.items():
        if entry.get("text_sha"):
            by_text.setdefault(entry["text_sha"], stem)
        elif entry.get("struct"):
            by_struct.setdefault(entry["struct"], stem)

    by_name = {}
    for stem, names in name_map.items():
        for name in names:
            by_name.setdefault(name, stem)

    return by_text, by_struct, by_name


# --- Reporting ---------------------------------------------------------------

def _human(n: int) -> str:
    """Byte count at a readable scale -- a reading list spans KB scans to GB atlases."""
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= scale:
            return f"{n / scale:.1f} {unit}"
    return f"{n} B"


# --- Ledger ------------------------------------------------------------------

def _open_ledger(log_path: str):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    is_new = not os.path.exists(log_path) or os.path.getsize(log_path) == 0
    handle = open(log_path, "a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
    if is_new:
        writer.writeheader()
    return handle, writer


# --- Actions -----------------------------------------------------------------

def _quarantine(pdf: Path, folder: Path) -> Path:
    """
    Move a duplicate into _duplicates/, without ever overwriting what is there.

    The default instead of unlink because tier 4 is a threshold and tier 5 is a
    coincidence: both can be wrong, and a deleted book is only recoverable by
    downloading it again.
    """
    dest_dir = folder / QUARANTINE_DIR
    dest_dir.mkdir(exist_ok=True)

    dest = dest_dir / pdf.name
    n = 1
    while dest.exists():
        dest = dest_dir / f"{pdf.stem} ({n}){pdf.suffix}"
        n += 1

    shutil.move(str(pdf), str(dest))
    return dest


def _resolve(fp: dict, keeper_path: Path, folder: Path,
             delete: bool, prefer_incoming: bool) -> str:
    """Apply the decision to disk. Returns the action recorded in the log."""
    if prefer_incoming and fp["size"] > keeper_path.stat().st_size:
        # Same path, better bytes: every database key stays valid, and
        # compress_pdf's ledger notices the size change and re-compresses it.
        os.replace(str(fp["path"]), str(keeper_path))
        return "replaced-keeper"

    if delete:
        fp["path"].unlink()
        return "deleted"

    _quarantine(fp["path"], folder)
    return "quarantined"


# --- Driver ------------------------------------------------------------------

def dedupe_all(src=None, incoming=None, dry_run=False, delete=False,
               prefer_incoming=False, structural=False,
               threshold=FUZZY_THRESHOLD,
               cache_path=dedupe_cache_path, log_path=dedupe_log_path) -> None:
    """
    Screen the not-yet-renamed PDFs in `incoming` against the library in `src`.

    Incoming files are the ones that are not already named <sha256>.pdf, which is
    exactly the set --renameFile is about to pull into the library. Running first
    means this stage sees the download name -- worth recording, and worth matching
    on -- while it still exists.
    """
    folder = Path(src or pdf_path)
    if not folder.is_dir():
        print(f"[ERROR] Reading list folder not found: {folder}")
        print("  Set READING_LIST_PATH in your .env file.")
        sys.exit(1)

    staging = Path(incoming) if incoming else folder
    if not staging.is_dir():
        print(f"[ERROR] Incoming folder not found: {staging}")
        sys.exit(1)

    if not (HAVE_FITZ or HAVE_PYPDF):
        print("[ERROR] Neither PyMuPDF nor pypdf is installed -- no way to read PDF text.")
        print("  Install one:  pip install pymupdf   or   pip install pypdf")
        sys.exit(1)

    new_files = sorted(
        staging / n for n in os.listdir(staging)
        if n.lower().endswith(".pdf") and not HASH_NAME_PATTERN.match(n)
        and (staging / n).is_file()
    )

    print(f"Library     : {folder}")
    print(f"Incoming    : {staging}")
    print(f"Backend     : {'PyMuPDF' if HAVE_FITZ else 'pypdf'}")
    print(f"Fuzzy       : Jaccard >= {threshold} over {SHINGLE_K}-gram shingles")
    print(f"Structural  : {'acted on' if structural else 'reported only (--dedupeStructural to act)'}")
    print(f"On match    : {_policy(dry_run, delete, prefer_incoming)}")
    print(f"To screen   : {len(new_files)} file(s)")
    print()

    if not new_files:
        print("Nothing to screen -- every PDF in the folder is already hash-named.")
        return

    cache = load_cache(cache_path)
    index = build_index(folder, cache)
    name_map = load_name_map(str(folder))
    by_text, by_struct, by_name = _lookups(index, name_map)
    print()

    handle = writer = None
    if not dry_run:
        handle, writer = _open_ledger(log_path)

    state = {"counts": {}, "dirty": False, "freed": 0}
    unmatched = []          # files that matched nothing in the library
    total = len(new_files)

    def act(fp, keeper, keeper_path, tier, score, label):
        """Record, resolve and report one duplicate. `keeper` is always a stem."""
        keeper_bytes = keeper_path.stat().st_size if keeper_path.exists() else 0

        if dry_run:
            action = "would-" + _policy_verb(delete, prefer_incoming, fp["size"], keeper_bytes)
        else:
            # Recorded before the file is touched: once it is moved or deleted,
            # its download name is the only thing that was lost.
            state["dirty"] |= record_original_name(name_map, keeper, fp["name"])
            try:
                action = _resolve(fp, keeper_path, folder, delete, prefer_incoming)
            except OSError as e:
                print(f"  {label} [{'LOCKED':<16}] {fp['name'][:36]:<36} {e}")
                state["counts"]["locked"] = state["counts"].get("locked", 0) + 1
                return
            writer.writerow({
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "action": action, "incoming": fp["name"],
                "incoming_bytes": fp["size"], "keeper": keeper,
                "keeper_bytes": keeper_bytes, "tier": tier, "score": score,
            })
            handle.flush()

        if action != "replaced-keeper":
            state["freed"] += fp["size"]
        state["counts"][action] = state["counts"].get(action, 0) + 1
        print(f"  {label} [{'DUP ' + tier:<16}] {fp['name'][:36]:<36} "
              f"{_human(fp['size']):>9} -> {keeper[:12]}...  {action}")

    try:
        for i, pdf in enumerate(new_files, 1):
            label = f"[{i:>4}/{total}]"
            try:
                fp = fingerprint_incoming(pdf)
            except OSError as e:
                print(f"  {label} [{'ERROR':<16}] {pdf.name[:36]:<36} {e}")
                state["counts"]["error"] = state["counts"].get("error", 0) + 1
                continue

            hit = find_match(fp, index, by_text, by_struct, by_name, threshold)

            if not hit:
                # The normalised text is the biggest thing in a fingerprint and is
                # no longer needed once matching is done -- dropping it is what
                # makes holding every unmatched file for the second pass cheap.
                fp["norm"] = ""
                fp["label"] = label
                unmatched.append(fp)
                continue

            keeper, tier, score = hit

            # Tier 5 is a coincidence, not proof. Report and move on.
            if tier == TIER_STRUCT and not structural:
                state["counts"]["needs-review"] = state["counts"].get("needs-review", 0) + 1
                print(f"  {label} [{'REVIEW':<16}] {pdf.name[:36]:<36} "
                      f"{_human(fp['size']):>9} ~  {keeper[:12]}...  page count + size only")
                continue

            act(fp, keeper, folder / (keeper + ".pdf"), tier, score, label)

        # Second pass: an incoming batch can hold the same book twice over. This
        # is resolved after the library pass, not during it, so the survivor can
        # be chosen by size -- if one copy is compressed and one is not, keeping
        # the larger means the library gets the original rather than whichever
        # happened to be read first.
        groups = {}
        for fp in unmatched:
            key = ("t", fp["text_sha"]) if fp["text_sha"] else (
                  ("b", fp["sha256"]) if fp["sha256"] else None)
            if key:
                groups.setdefault(key, []).append(fp)

        twins = set()
        for members in groups.values():
            if len(members) < 2:
                continue
            members.sort(key=lambda f: (-f["size"], f["name"]))
            survivor = members[0]
            for loser in members[1:]:
                twins.add(id(loser))
                # The survivor is not in the library yet, so its stem is the name
                # --renameFile is about to give it. Recording under that keeps
                # _original_names.json keyed by sha256, as catalog.py expects.
                act(loser, survivor["sha256"], survivor["path"],
                    "incoming-twin", 1.0, loser["label"])

        for fp in unmatched:
            if id(fp) in twins:
                continue
            state["counts"]["unique"] = state["counts"].get("unique", 0) + 1
            print(f"  {fp['label']} [{'NEW':<16}] {fp['name'][:36]:<36} {_human(fp['size']):>9}")

    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Files already resolved are logged; re-run to continue.")
    finally:
        if handle:
            handle.close()
        if state["dirty"]:
            save_name_map(str(folder), name_map)
        # Saved even on a dry run. The cache is derived data, not a change to the
        # library, and a dry run is exactly what gets run first -- making it pay
        # the full index cost again on the real run would be a pointless four
        # minutes over a 2,750-book library.
        save_cache(index, cache_path)

    counts, freed = state["counts"], state["freed"]
    print()
    for action, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {action:<18} {n}")
    if freed:
        print(f"\n{_human(freed)} of duplicate PDFs "
              f"{'would be' if dry_run else 'was'} taken out of the reading list.")
    if counts.get("needs-review"):
        print(f"\n{counts['needs-review']} scanned book(s) matched on page count and page "
              f"size alone.\n  Check them, then re-run with --dedupeStructural to act on them.")
    if dry_run:
        print("\n--dedupeDryRun: nothing written.")
    elif counts.get("quarantined"):
        print(f"\nDuplicates moved to {folder / QUARANTINE_DIR}. Delete that folder once "
              f"you are satisfied.")


def _policy(dry_run, delete, prefer_incoming):
    if dry_run:
        return "report only (--dedupeDryRun)"
    what = "delete the incoming copy" if delete else f"move it to {QUARANTINE_DIR}/"
    if prefer_incoming:
        return f"keep the larger copy under the library's name, else {what}"
    return what


def _policy_verb(delete, prefer_incoming, incoming_bytes, keeper_bytes):
    if prefer_incoming and incoming_bytes > keeper_bytes:
        return "replace-keeper"
    return "delete" if delete else "quarantine"


# --- Sweep: duplicates already sitting in the library ------------------------

def sweep(src=None, dry_run=False, delete=False, structural=False,
          cache_path=dedupe_cache_path, log_path=dedupe_log_path) -> None:
    """
    Find books that are already in the library twice, under two different stems.

    This is the backlog case: pairs that got in before this stage existed. Both
    copies are hash-named and both may be registered in the database, so unlike
    dedupe_all there is no "incoming" to prefer -- the keeper is chosen by a fixed
    rule, and the loser's rows are cleaned up by --buildCatalog on its next run
    (catalog.py drops book_catalog rows whose hash is no longer on disk).

    Keeper preference: the copy that has been through --pdfToText, then the older
    file, then the lexicographically smaller stem so the choice is deterministic.

    Exact text matching only, no fuzzy tier: both sides' text came out of the same
    extractor in modules/pdf_to_txt.py, so a genuine pair matches exactly or is a
    different scan of the book -- which is a judgement call, not a dedup.
    """
    folder = Path(src or pdf_path)
    if not folder.is_dir():
        print(f"[ERROR] Reading list folder not found: {folder}")
        sys.exit(1)

    cache = load_cache(cache_path)
    index = build_index(folder, cache)
    name_map = load_name_map(str(folder))

    groups = {}
    for stem, entry in index.items():
        if entry.get("text_sha"):
            groups.setdefault(("text", entry["text_sha"]), []).append(stem)
        elif structural and entry.get("struct"):
            groups.setdefault(("struct", entry["struct"]), []).append(stem)

    dupes = {k: v for k, v in groups.items() if len(v) > 1}
    print(f"\nGroups with more than one copy: {len(dupes)}")
    if not dupes:
        print("No duplicate books found in the library.")
        save_cache(index, cache_path)
        return

    handle = writer = None
    if not dry_run:
        handle, writer = _open_ledger(log_path)

    dirty, removed, freed = False, 0, 0

    try:
        for (kind, _), stems in sorted(dupes.items()):
            stems.sort(key=lambda s: _keeper_rank(folder, s))
            keeper, losers = stems[0], stems[1:]
            tier = TIER_TEXT if kind == "text" else TIER_STRUCT

            print(f"\n  KEEP {keeper[:16]}...  ({_human(index[keeper].get('size', 0))}, {tier})")
            for loser in losers:
                path = folder / (loser + ".pdf")
                size = index[loser].get("size", 0)
                print(f"    DROP {loser[:16]}...  ({_human(size)})")

                if dry_run:
                    continue

                # The loser's recorded download names belong to the same book.
                for name in name_map.get(loser, []):
                    dirty |= record_original_name(name_map, keeper, name)

                try:
                    if delete:
                        path.unlink()
                        action = "deleted"
                    else:
                        _quarantine(path, folder)
                        action = "quarantined"
                except OSError as e:
                    print(f"      [LOCKED] {e}")
                    continue

                index.pop(loser, None)
                name_map.pop(loser, None)
                dirty = True
                removed += 1
                freed += size

                writer.writerow({
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "action": "sweep-" + action, "incoming": loser + ".pdf",
                    "incoming_bytes": size, "keeper": keeper,
                    "keeper_bytes": index[keeper].get("size", 0),
                    "tier": tier, "score": 1.0,
                })
                handle.flush()
    finally:
        if handle:
            handle.close()
        if dirty:
            save_name_map(str(folder), name_map)
        save_cache(index, cache_path)   # derived data -- see dedupe_all

    print()
    if dry_run:
        print("--dedupeDryRun: nothing written.")
    else:
        print(f"{removed} duplicate copy(ies) removed, {_human(freed)} freed.")
        print("Run --buildCatalog to drop the stale book_catalog rows.")


def _keeper_rank(folder: Path, stem: str):
    """
    Sort key for choosing which copy of a book to keep.

    Extracted text first -- that copy has been through the pipeline and has rows
    downstream. Then the LARGEST, because when a pair has identical text and
    different sizes the big one is the pre-compression original and the small one
    has already lost image quality; that loss is permanent, and keeping the
    original costs nothing but a re-run of --compressPDF. Then oldest, then the
    stem, so the choice never depends on directory order.
    """
    txt = Path(source_data) / (stem + ".txt")
    try:
        has_text = 0 if txt.stat().st_size > 0 else 1
    except OSError:
        has_text = 1
    try:
        st = (folder / (stem + ".pdf")).stat()
        size, mtime = st.st_size, st.st_mtime
    except OSError:
        size, mtime = 0, float("inf")
    return (has_text, -size, mtime, stem)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="De-duplicate the reading list by content, not by bytes.")
    ap.add_argument("--source", default=None, help="library folder (default: READING_LIST_PATH)")
    ap.add_argument("--incoming", default=None, help="folder of new downloads (default: the library folder)")
    ap.add_argument("--sweep", action="store_true", help="compare the library against itself instead of screening new files")
    ap.add_argument("--dryRun", action="store_true", help="report what would happen, write nothing")
    ap.add_argument("--delete", action="store_true", help="delete duplicates instead of moving them to _duplicates/")
    ap.add_argument("--preferIncoming", action="store_true", help="keep the larger copy's bytes under the library copy's name")
    ap.add_argument("--structural", action="store_true", help="also act on scans matched by page count and page size alone")
    ap.add_argument("--threshold", type=float, default=FUZZY_THRESHOLD, help="Jaccard threshold for the fuzzy tier (default: %(default)s)")
    a = ap.parse_args()

    if a.sweep:
        sweep(src=a.source, dry_run=a.dryRun, delete=a.delete,
              structural=a.structural)
    else:
        dedupe_all(src=a.source, incoming=a.incoming, dry_run=a.dryRun,
                   delete=a.delete, prefer_incoming=a.preferIncoming,
                   structural=a.structural, threshold=a.threshold)
