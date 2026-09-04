"""
Table lifecycle for the Python stages.

Every CREATE TABLE / CREATE INDEX lives in config/schema.sql and nowhere else;
src/lib/schema.hpp loads the same file, so the two sides cannot drift. Before
this existed, `tf_idf` was declared twice with two different shapes and whichever
stage ran first on a fresh database silently won.

    apply(conn)                 create anything missing (idempotent)
    reset(conn, [...])          drop those tables, then re-apply
    require(conn, {...}, flag)  check a stage's inputs before it does any work
    expected(), compare(conn)   what --dbDoctor uses to report drift
"""

import sqlite3

from modules.path import schema_sql_path

# Tables config/schema.sql deliberately does not declare, so the doctor does not
# report them as strays. See the header of that file for why each is excluded.
UNMANAGED_TABLES = {
    # src/modules/catalog.py owns these and self-rebuilds them.
    'book_catalog', 'book_user_meta', 'catalog_meta',
    # CREATE TABLE ... AS SELECT snapshots rebuilt by --runCutoffAnalysis.
    'freq_dist', 'token_dist', 'file_dist', 'word_dist', 'totals', 'cutoff_analysis',
}


def schema_text():
    """
    Read config/schema.sql.

    A missing file means the process is running from the wrong directory rather
    than something recoverable -- the file ships with the source.
    """
    try:
        with open(schema_sql_path, 'r', encoding='utf-8') as f:
            return f.read()
    except OSError as exc:
        raise RuntimeError(
            f"Cannot read schema file: {schema_sql_path}\n"
            f"Run the pipeline from the project root, where config/schema.sql lives."
        ) from exc


def statements(text=None):
    """
    Split config/schema.sql into individual statements.

    Used instead of executescript() because that issues a COMMIT before it runs,
    which would break an enclosing transaction -- scripts/migrate_ids.py applies
    the schema partway through one. The file holds no string literals containing
    ';' or '--', so stripping comments and splitting is enough.
    """
    body = "\n".join(line.split('--')[0] for line in (text or schema_text()).splitlines())
    return [s.strip() for s in body.split(';') if s.strip()]


def apply(conn, commit=True):
    """
    Create every pipeline table and index that does not exist yet.

    Idempotent -- every statement is IF NOT EXISTS -- so a stage can call this on
    entry without caring what ran before it. Pass commit=False to apply inside a
    transaction the caller is managing.
    """
    for statement in statements():
        conn.execute(statement)
    if commit:
        conn.commit()


def reset(conn, tables):
    """
    Drop the named tables, then rebuild them from config/schema.sql.

    Dropping and recreating happen in one call so they cannot drift apart, and
    the re-apply is not optional: dropping a table drops its indexes too.
    """
    for table in tables:
        conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    apply(conn)


def has_rows(conn, table):
    """
    True when the table exists and holds at least one row.

    Emptiness counts as absence on purpose: an upstream stage that created its
    table and wrote nothing leaves the same hole for the stage that follows.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return False
    return conn.execute(f'SELECT EXISTS(SELECT 1 FROM "{table}" LIMIT 1)').fetchone()[0] == 1


def require(conn, inputs, stage):
    """
    Check a stage's inputs before it does any work.

    `inputs` maps table name -> the command that produces it. Returns False and
    prints what to run, so a stage says what is missing instead of dying on an
    SQL error several statements in.
    """
    missing = {t: producer for t, producer in inputs.items() if not has_rows(conn, t)}
    if not missing:
        return True

    noun = "input is" if len(missing) == 1 else "inputs are"
    print(f"[{stage}] cannot run: {len(missing)} {noun} missing or empty.")
    for table, producer in missing.items():
        print(f"    {table} <- run {producer} first")
    return False


def expected():
    """
    The schema config/schema.sql describes, as {table: {'columns': [...], 'pk': [...]}}
    plus {'_indexes': [...]}.

    Built by applying the file to an in-memory database rather than parsing SQL,
    so whatever SQLite understands is what gets compared.
    """
    mem = sqlite3.connect(':memory:')
    apply(mem)
    return _describe(mem)


def _describe(conn):
    """Snapshot a connection's tables, columns and indexes for comparison."""
    # Indexes on unmanaged tables (catalog.py's idx_catalog_*) are excluded the
    # same way their tables are, so they are never reported as strays.
    out = {'_indexes': sorted(
        name for name, tbl in conn.execute(
            "SELECT name, tbl_name FROM sqlite_master "
            "WHERE type='index' AND name NOT LIKE 'sqlite_%'")
        if tbl not in UNMANAGED_TABLES
    )}

    for (table,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
        if table in UNMANAGED_TABLES:
            continue
        cols, pk = [], []
        for _cid, name, ctype, notnull, default, pk_pos in conn.execute(
                f'PRAGMA table_info("{table}")'):
            cols.append((name, ctype.upper(), bool(notnull), default))
            if pk_pos:
                pk.append((pk_pos, name))
        out[table] = {'columns': cols, 'pk': [n for _, n in sorted(pk)]}

    return out


def compare(conn):
    """
    Diff a live database against config/schema.sql.

    Returns a list of human-readable drift descriptions; empty means the database
    matches the file. Compares PRAGMA table_info rather than raw DDL text, so
    reformatting the .sql file never registers as drift.
    """
    want, have = expected(), _describe(conn)
    problems = []

    for table in sorted(set(want) | set(have)):
        if table == '_indexes':
            continue
        if table not in have:
            problems.append(f"missing table: {table}")
        elif table not in want:
            problems.append(f"table not declared in schema.sql: {table}")
        else:
            if want[table]['columns'] != have[table]['columns']:
                want_cols = {c[0] for c in want[table]['columns']}
                have_cols = {c[0] for c in have[table]['columns']}
                if want_cols - have_cols:
                    problems.append(f"{table}: missing columns {sorted(want_cols - have_cols)}")
                if have_cols - want_cols:
                    problems.append(f"{table}: undeclared columns {sorted(have_cols - want_cols)}")
                if want_cols == have_cols:
                    problems.append(f"{table}: column types/constraints differ from schema.sql")
            if want[table]['pk'] != have[table]['pk']:
                problems.append(
                    f"{table}: primary key is {have[table]['pk']}, schema.sql says {want[table]['pk']}")

    for index in sorted(set(want['_indexes']) - set(have['_indexes'])):
        problems.append(f"missing index: {index}")
    for index in sorted(set(have['_indexes']) - set(want['_indexes'])):
        problems.append(f"index not declared in schema.sql: {index}")

    return problems
