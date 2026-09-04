# Book Catalog Dataset

**Goal:** a first-class, structured **book catalog** — one authoritative record per PDF in
the reading list — so the library is queryable metadata (title, subject domain, topics,
length, text-layer health, processing status) instead of thousands of hash-named files plus
a scattered set of derived tables.

**Status: shipped.** `modules/catalog.py` builds it, `--buildCatalog` runs it, and it is
part of the default end-to-end pipeline in `config/main.bat` / `config/main.sh`.

```
python src/main.py --buildCatalog     # build the table + exports
python src/main.py --catalogStats     # print coverage without rebuilding
python src/main.py --buildCatalog --noProbe   # skip PDF probing (fast metadata rebuild)
```

---

## 1. Why this exists

The library used to be understood only through side effects of the NLP pipeline. The facts
were spread across four places that never got joined into a per-book view:

| Where the truth lives | What it holds | What was missing |
|---|---|---|
| `books/*.pdf` | the files themselves, named by SHA-256 | no titles, no metadata |
| `books/_original_names.json` | SHA-256 → real filename(s) | partial coverage; no subjects |
| `pdf_text.db → file_info / file_token` | chunk counts, token stats | keyed by a *different* id; no titles |
| `pdf_text.db → tags_full` | topic tags per file | noisy, partial coverage |

There was no single table you could `SELECT` to answer "what books do I have on control
theory, how long are they, and are they processed yet?" — which is exactly what the GUI
recommender and any future dataset work needs.

**For current coverage numbers, run `--catalogStats`.** They are deliberately not written
down here: the previous version of this document hard-coded a snapshot that was stale within
a day of being measured.

---

## 2. The dataset — schema

One row per PDF in table **`book_catalog`**, plus CSV/JSON exports in `data/catalog/`.

### Identity and key translation

The library uses three key spaces, and before the catalog every consumer re-derived them by
hand. `book_catalog` is now the one place they meet:

| Column | Value | Joins to |
|---|---|---|
| `hash_id` (PK) | SHA-256, the disk filename stem | `file_info.file_name`, `_original_names.json` |
| `title_id` | `'title_' \|\| file_info.id`, where `id` = `md5(hash_id)` | `file_token`, `tags`, `tags_full`, `comparison`, `item_matrix`, `relation_distance_filtered` |
| `txt_name` | `<hash>.txt` | `pdf_chunks.file_name` |

### Bibliographic

| Column | Source | Notes |
|---|---|---|
| `title` | `_original_names.json` → PDF metadata | cleaned of the `_YY_MM_DD_...` download suffix |
| `title_source` | derived | `name_map` \| `pdf_meta` \| `unknown` |
| `domain` | classifier | 18 coarse buckets (§3) |
| `domain_source` | derived | `title` \| `topics` \| `none` — which evidence decided it |
| `domain_confidence` | derived | winner's share of all keyword matches; 1.0 = nothing else matched |
| `domain_matches` | derived | raw keyword count, so thin evidence stays visible |
| `primary_topic` / `topics` | `tags_full` | strongest tag / top-8, `; `-joined |
| `pdf_title` / `pdf_author` / `pdf_producer` / `pdf_year` | PDF metadata | raw embedded values |

### Text-layer health

`processed` alone conflated "never attempted" with "scanned PDF, no text layer" — only the
second needs OCR. These split them:

| Column | Notes |
|---|---|
| `processed` | 1 = present in `file_info` (text extracted into the DB) |
| `text_status` | `ok` \| `empty` (no text layer — **OCR candidate**) \| `missing` (not converted yet) |
| `text_bytes` | size of `data/raw_text/<hash>.txt` |
| `language` | best-effort, `und` when thin or ambiguous — the NLP stack assumes English |

### Size, provenance, integrity

| Column | Notes |
|---|---|
| `page_count`, `file_size_bytes`, `needs_password` | physical facts |
| `chunk_count`, `total_tokens`, `unique_tokens`, `relational_distance` | existing pipeline metrics |
| `download_copies` | >1 ⇒ re-downloaded under a different name (already de-duplicated on disk) |
| `orphan_title_id` | 1 = this row's `title_id` matches nothing in `file_token` (see §6) |
| `file_path` | absolute path |

Two companion tables:

- **`book_user_meta`** (`hash_id`, `read_status`, `rating`, `notes`, `updated_at`) — anything
  a human enters. The builder never writes it, so a schema change can rebuild the whole
  catalog without destroying reading progress.
- **`catalog_meta`** — how this build was made: `catalog_version`, `built_at`, `chunk_size`,
  `chunk_overlap`, `chunk_unit`, `probe_backend`, `reading_list_path`. Also exported as
  `data/catalog/catalog_meta.json` and as the `meta` block of `catalog.json`.

**Query through the `v_book` view**, not the raw table — it is `book_catalog` left-joined to
`book_user_meta`, and it spares every call site from rebuilding `'title_' || file_info.id`
by hand.

---

## 3. Subject classification

`tags_full` alone is too noisy to categorize with, so the classifier is **title-first**: the
real title is matched against an 18-domain keyword taxonomy, and only when the title yields
nothing do the topic tags get a turn. Domains: AI & ML, Data & Analytics, Energy &
Sustainability, Healthcare & Medicine, Biology & Life Sciences, Materials & Chemistry,
Electrical & Electronics, Networks/IoT & Security, Mechanical & Manufacturing, Civil &
Construction, Control & Automation, Mathematics & Statistics, Physics & Astronomy, Earth &
Environmental Science, Business & Management, Social Sciences & Humanities, Agriculture &
Food, and Other/Uncategorized.

**All 18 domains are scored and the highest wins.** The first version returned the first
domain whose pattern matched at all, which let broad patterns sitting early in the list win
every tie — Energy & Sustainability collected 18% of the library that way. Ties now break
alphabetically rather than by list position, and `domain_confidence` exposes how close the
call was.

This is still a keyword heuristic. §7 covers upgrading it to the app's own TF-IDF/topic
engine, which is the right long-term classifier.

---

## 4. Where it plugs into the pipeline

The catalog is a **read-mostly** stage that runs *after* extraction and tagging and never
mutates existing tables:

```
--renameFile ─▶ --pdfToText ─▶ --extractText ─▶ --processWordFreq ─▶ word_tokenizer --computeTFIDF
      │                                                 │                      │
      │                                                 └──▶ --topicTokenize ──┘
      │                                                             │
      │                                                             ▼
      └── writes _original_names.json ────────────────────▶ --buildCatalog
                                                   (join everything → book_catalog + exports)
```

`modules/catalog.py` reads paths only from `modules.path` (`pdf_path`,
`chunk_database_path`, `data_folder`, `source_data`) — no new config, no hard-coded paths.

### `--renameFile` owns the title map

`rename_files()` renames each PDF to `<sha256>.pdf` and deletes content-duplicates. Both
throw away the original filename — which is the only human-readable record of what a book
is. It therefore **appends the original name to `_original_names.json` before touching the
file**, atomically (temp file + `os.replace`).

This is what keeps the catalog from decaying: `title_source='name_map'` coverage now grows
with every batch of downloads instead of shrinking, and `download_copies` is a measured count
rather than an inference from a hand-maintained file.

---

## 5. Performance & the two caches

Everything expensive here is per-file disk I/O, and the library lives on a slow volume. The
database side is not the problem: reading the three pipeline tables, writing all 2,600+ rows
and exporting CSV/JSON together take **under half a second**. Measured on the current
library:

| Run | Time |
|---|---|
| First build, nothing cached | 656 s |
| Full re-probe, text cached | 194 s |
| Steady state (only new books) | **1.4 s** |

Two independent caches get it there, both stored in `book_catalog` itself:

- **Probe cache** — page count and embedded metadata. Only *new* files are probed; adding 10
  books probes 10 files, not thousands. A row with no page count counts as never
  successfully probed and is retried rather than caching the failure forever. `PROBE_VERSION`
  invalidates the whole cache when the probe logic changes — without it, a fix to the
  metadata parsing would never reach rows already cached.
- **Text cache** — `text_bytes` + `language`. The `.txt` is re-opened only when its size
  changed. This, not the PDF probe, was the dominant cost: sampling text from every book was
  roughly 460 s of the original 656 s build.

Probing uses **PyMuPDF** (already `pdf_to_txt.py`'s extraction backend), falling back to
poppler's `pdfinfo` only if PyMuPDF is unavailable — poppler is not installed on every
machine that runs this pipeline, and PyMuPDF avoids one subprocess per file. `--noProbe`
skips probing entirely.

Progress is printed every 250 books, so a stalled file is visible rather than being ten
silent minutes.

**Rebuilds are non-destructive.** Rows are upserted on `hash_id` and rows for files no longer
on disk are removed. If `COLS` changes, `book_catalog` is rebuilt from scratch — it is 100%
derived, so this costs only a re-probe — while `book_user_meta` is left untouched.

---

## 6. Resolved: `file_info.id` is now derived from the file's *name*

`create_unique_id` in `src/lib/updateDB.hpp` used to hash the **absolute path**, so moving
the library or editing `READING_LIST_PATH` silently re-keyed every derived table —
`file_token`, `tags`, `tags_full`, `comparison`, `item_matrix`,
`relation_distance_filtered` — with no error anywhere. It also forced `--compressPDF` to
rewrite each PDF at its own path and `--dedupePDF` to always keep the library copy.

It now hashes the **stem**, which `--renameFile` has already set to the sha256 of the file's
contents. The id is `md5(stem)`, still 32 hex characters, so every `title_<id>` value kept
its shape and no consumer changed. `scripts/migrate_ids.py` performed the one-time re-key
(2026-08-27): it rebuilds each keyed table through a mapping of old id to new, renames
`data/token_json/title_<id>.json`, rewrites `data/low_similarity.txt`, and records
`pipeline_meta.id_scheme = 'content-md5'`. It is idempotent and refuses to run twice.

What remains true: **renaming a book still orphans its derived rows.** Where the library
sits does not matter; what it calls each file does.

Two checks make any breakage loud. `orphan_title_id` flags a row whose `title_id` has no
`file_token` row and `--catalogStats` prints the total; `python src/main.py --dbDoctor`
checks the same across every derived table, plus schema drift against `config/schema.sql`,
ids that predate the migration, and `file_info` rows whose PDF is gone from disk.

---

## 7. Upgrade path

- **Better subjects.** `tags_full` already scores every file against a topic vocabulary via
  TF-IDF relational distance. Map the fine-grained topics onto the 18 coarse domains once (a
  topic→domain lookup), then derive `domain` from each file's strongest tags instead of its
  title. Reuses machinery that already exists.
- **Embed titles.** `chromadb` / `langchain-chroma` are declared in `src/env.yml`, but
  nothing in the codebase uses them yet and `vector_db/` is empty — wiring `book_catalog`
  into a vector store as document-level metadata is a **new component**, not a small add-on.
- **Full-text search.** The GUI's Content Search is `LIKE '%kw%'` over every chunk; on the
  current corpus a single query takes minutes. An external-content FTS5 index over
  `pdf_chunks` would make it instant and add `snippet()`/`bm25()` ranking, without storing a
  second copy of the text. Deliberately deferred, not overlooked.
- Keep `title_source`, `download_copies`, `text_status` and `orphan_title_id` regardless —
  they're facts, not guesses, and they're what tell you which rows to trust.

---

## 8. Files

- `docs/CATALOG_DATASET_PLAN.md` — this document.
- `src/modules/catalog.py` — the builder.
- `src/modules/extract_text.py` — owns `_original_names.json` and the chunking constants
  the catalog records as provenance.
- `data/catalog/catalog.csv` · `catalog.json` · `catalog_meta.json` — **build artifacts**,
  regenerated by `--buildCatalog`. `data/` is gitignored; these are not committed.
