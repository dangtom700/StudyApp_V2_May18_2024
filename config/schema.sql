-- ============================================================================
-- Canonical schema for data/pdf_text.db
--
-- This file is the ONLY place a pipeline table is defined. Both sides load it:
--   C++     SCHEMA::apply(db)      src/lib/schema.hpp
--   Python  schema.apply(conn)     src/modules/schema.py
--
-- Before this file existed the same table could be created in two places with
-- two different shapes -- `tf_idf` was declared WITHOUT ROWID / NOT NULL in
-- src/lib/feature.hpp and as a nullable rowid table in src/modules/tf_idf.py,
-- and whichever stage ran first on a fresh database silently won, because both
-- used CREATE TABLE IF NOT EXISTS. Every statement here is still IF NOT EXISTS,
-- so applying it is idempotent and safe to run at the top of any stage.
--
-- Rules
--   * A stage never writes DDL of its own. To reset its output it drops the
--     tables it owns (SCHEMA::reset / schema.reset) and re-applies this file.
--   * Changing a column here does NOT migrate an existing table: SQLite skips
--     the CREATE when the table exists. Ship a migration in scripts/ and bump
--     pipeline_meta.schema_version.
--   * `python src/main.py --dbDoctor` compares the live database against this
--     file and reports drift.
--
-- Not declared here, on purpose:
--   * book_catalog / book_user_meta / catalog_meta and their idx_catalog_*
--     indexes -- src/modules/catalog.py owns them and self-rebuilds when its
--     COLS list changes (see _ensure_schema there).
--   * freq_dist, token_dist, file_dist, word_dist, totals, cutoff_analysis --
--     CREATE TABLE ... AS SELECT snapshots that --runCutoffAnalysis rebuilds
--     from scratch on every run. Their shape follows their query.
--   * temp_tokens -- a per-connection TEMP table in src/lib/recommend.hpp.
-- ============================================================================


-- --- provenance -------------------------------------------------------------

-- Written by migrations and read by --dbDoctor. Keys in use:
--   schema_version  integer, bumped by each migration in scripts/
--   id_scheme       'path-md5' (legacy) | 'content-md5' (see scripts/migrate_ids.py)
CREATE TABLE IF NOT EXISTS pipeline_meta (
    key   TEXT NOT NULL PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;


-- --- documents --------------------------------------------------------------

-- Owner: src/main.py --extractText (src/modules/extract_text.py)
-- file_name is "<sha256>.txt" -- the extracted text file, not the PDF.
CREATE TABLE IF NOT EXISTS pdf_chunks (
    file_name  TEXT,
    chunk_id   INTEGER,
    chunk_text TEXT NOT NULL,
    PRIMARY KEY (file_name, chunk_id)
);

-- Owner: word_tokenizer --updateDatabaseInformation (computeResourceData)
-- file_name is the PDF's stem: the sha256 of its contents, no extension.
-- id is md5(file_name) -- content-derived, so it survives the library moving.
-- Every derived table below keys off 'title_' || id.
CREATE TABLE IF NOT EXISTS file_info (
    id          TEXT    NOT NULL UNIQUE,
    file_name   TEXT    NOT NULL PRIMARY KEY,
    file_path   TEXT    NOT NULL DEFAULT '',
    epoch_time  INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0
);


-- --- token statistics -------------------------------------------------------

-- Owner: word_tokenizer --computeRelationalDistance
-- file_name here is 'title_' || file_info.id, taken from the token_json stem.
CREATE TABLE IF NOT EXISTS file_token (
    file_name           TEXT    NOT NULL PRIMARY KEY,
    total_tokens        INTEGER NOT NULL DEFAULT 0,
    unique_tokens       INTEGER NOT NULL DEFAULT 0,
    relational_distance REAL    NOT NULL DEFAULT 0.0
) WITHOUT ROWID;

-- Owner: word_tokenizer --computeRelationalDistance
CREATE TABLE IF NOT EXISTS relation_distance_filtered (
    file_name           TEXT    NOT NULL,
    token               TEXT    NOT NULL,
    frequency           INTEGER NOT NULL DEFAULT 0,
    relational_distance REAL    NOT NULL DEFAULT 0.0,
    PRIMARY KEY (file_name, token)
) WITHOUT ROWID;

-- The PK serves file_name lookups; this serves the other direction. Without it
-- every "which files contain this token" query is a full scan of ~1.9M rows,
-- which --labelTopics pays once per topic across ~2000 topics.
CREATE INDEX IF NOT EXISTS idx_rd_token
    ON relation_distance_filtered(token, file_name, relational_distance);

-- Owner: word_tokenizer --computeTFIDF
-- WITHOUT ROWID: word IS the b-tree key, so WHERE word = ? is one lookup.
CREATE TABLE IF NOT EXISTS tf_idf (
    word      TEXT    NOT NULL PRIMARY KEY,
    freq      INTEGER NOT NULL DEFAULT 0,
    doc_count INTEGER NOT NULL DEFAULT 0,
    tf_idf    REAL    NOT NULL DEFAULT 0.0
) WITHOUT ROWID;


-- --- document-to-document similarity ----------------------------------------
--
-- Two tables hold the same relation, computed two ways, and both are kept:
--
--   comparison   word_tokenizer --mappingItemMatrix   DEFAULT. Scores with
--                tf-idf folded into each token weight, cutoff 0.4. What
--                --expandTopics expands over and what app/ recommends from.
--   item_matrix  python src/main.py --computeItemMatrix   The fast variant:
--                one sparse matrix product, cutoff 0.3, and the only table
--                carrying distance_mod. Read by scripts/note_generator.py.
--
-- Both store each unordered pair once, so readers must union both directions.

CREATE TABLE IF NOT EXISTS comparison (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    distance  REAL NOT NULL DEFAULT 0.0 CHECK(distance > 0.0),
    PRIMARY KEY (source_id, target_id)
) WITHOUT ROWID;

-- The PK covers source_id; expand_degree also joins on target_id.
CREATE INDEX IF NOT EXISTS idx_cmp_target ON comparison(target_id, distance);

CREATE TABLE IF NOT EXISTS item_matrix (
    source_id    TEXT NOT NULL,
    target_id    TEXT NOT NULL,
    distance     REAL NOT NULL DEFAULT 0.0,
    distance_mod REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (source_id, target_id)
) WITHOUT ROWID;


-- --- topics -----------------------------------------------------------------

-- Owner: python src/main.py --topicTokenize (src/modules/word_freq.py)
CREATE TABLE IF NOT EXISTS topic_token (
    topic               TEXT,
    token               TEXT,
    frequency           INTEGER,
    relational_distance REAL,
    PRIMARY KEY (topic, token)
);

-- Owner: word_tokenizer --labelTopics. Every (document, topic) score.
CREATE TABLE IF NOT EXISTS tags_full (
    ID       TEXT NOT NULL,
    distance REAL NOT NULL DEFAULT 0.0 CHECK(distance > 0.0),
    topic    TEXT NOT NULL,
    PRIMARY KEY (ID, topic)
) WITHOUT ROWID;

-- Owner: word_tokenizer --expandTopics. Seeded from tags_full above the degree-1
-- threshold, then widened along comparison edges one degree at a time.
CREATE TABLE IF NOT EXISTS tags (
    ID       TEXT    NOT NULL,
    distance REAL    NOT NULL CHECK(distance > 0 AND distance <= 1),
    topic    TEXT    NOT NULL,
    degree   INTEGER NOT NULL CHECK(degree >= 1),
    PRIMARY KEY (ID, topic)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_tags_degree ON tags(degree);

-- Owner: word_tokenizer --topicSimilarity
CREATE TABLE IF NOT EXISTS topic_similarity (
    source_topic TEXT NOT NULL,
    target_topic TEXT NOT NULL,
    distance     REAL NOT NULL DEFAULT 0.0 CHECK(distance > 0.0),
    PRIMARY KEY (source_topic, target_topic)
) WITHOUT ROWID;
