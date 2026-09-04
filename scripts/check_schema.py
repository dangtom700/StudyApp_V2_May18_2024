"""
Database doctor: everything that can quietly go wrong with the pipeline's tables.

    python src/main.py --dbDoctor       (or: python scripts/check_schema.py)
    python scripts/check_schema.py --dump    to print the raw DDL instead

It reports four kinds of trouble, each of which used to be found only by a stage
failing or -- worse -- by a stage succeeding against wrong data:

  schema drift    the live database no longer matches config/schema.sql
  orphans         derived rows keyed to a document file_info no longer knows
  id scheme       ids that predate the content-addressed key (scripts/migrate_ids.py)
  missing files   file_info rows whose PDF is no longer on disk

Exit status is 1 if anything was reported, so it can gate a pipeline run.
"""

import argparse
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import sqlite3
from modules import schema
from modules.path import chunk_database_path

# Derived tables and the column holding 'title_' || file_info.id.
KEYED_COLUMNS = {
    'file_token': ['file_name'],
    'relation_distance_filtered': ['file_name'],
    'comparison': ['source_id', 'target_id'],
    'item_matrix': ['source_id', 'target_id'],
    'tags': ['ID'],
    'tags_full': ['ID'],
    'book_catalog': ['title_id'],
}


def _exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)).fetchone() is not None


def check_drift(conn):
    """The live database against config/schema.sql."""
    return schema.compare(conn)


def check_orphans(conn):
    """
    Derived rows whose document is gone from file_info.

    Generalises the single-table orphan_title_id check in modules/catalog.py. A
    nonzero count means a join in the app or the catalog silently returns less
    than it should.
    """
    problems = []
    if not _exists(conn, 'file_info'):
        return ["file_info is missing -- run word_tokenizer --updateDatabaseInformation"]

    for table, columns in KEYED_COLUMNS.items():
        if not _exists(conn, table):
            continue
        for column in columns:
            n = conn.execute(
                f'SELECT COUNT(*) FROM "{table}" '
                f'WHERE substr("{column}", 7) NOT IN (SELECT id FROM file_info)'
            ).fetchone()[0]
            if n:
                problems.append(f"{table}.{column}: {n:,} rows key to a document "
                                f"file_info does not have")

    # The reverse direction: a document nothing downstream has processed yet.
    if _exists(conn, 'file_token'):
        n = conn.execute(
            "SELECT COUNT(*) FROM file_info WHERE chunk_count > 0 "
            "AND 'title_' || id NOT IN (SELECT file_name FROM file_token)"
        ).fetchone()[0]
        if n:
            problems.append(f"file_info: {n:,} documents with text have no file_token row "
                            f"-- run --processWordFreq then --computeRelationalDistance")

    n = conn.execute("SELECT COUNT(*) FROM file_info WHERE chunk_count = 0").fetchone()[0]
    if n:
        problems.append(f"file_info: {n:,} rows have chunk_count = 0, so every stage "
                        f"filtering on chunk_count > 0 skips them")

    return problems


def check_id_scheme(conn):
    """
    Whether file_info.id is what src/lib/updateDB.hpp derives today.

    Ids used to be md5 of the file's absolute path, which made them break whenever
    the library moved. They are now md5 of the stem. A mismatch here means the
    database predates that change and scripts/migrate_ids.py has not been run.
    """
    if not _exists(conn, 'file_info'):
        return []

    rows = conn.execute("SELECT id, file_name FROM file_info").fetchall()
    if not rows:
        return []

    stale = sum(1 for id_, stem in rows
                if id_ != hashlib.md5(stem.encode('utf-8')).hexdigest())
    if not stale:
        return []

    return [f"file_info: {stale:,} of {len(rows):,} ids are not md5(file_name). "
            f"This database is still on path-derived ids -- run "
            f"`python scripts/migrate_ids.py` (take a snapshot first)."]


def check_files_on_disk(conn):
    """file_info rows whose PDF is no longer where it was recorded."""
    if not _exists(conn, 'file_info'):
        return []

    missing = sum(1 for (p,) in conn.execute("SELECT file_path FROM file_info")
                  if p and not os.path.exists(p))
    if not missing:
        return []

    return [f"file_info: {missing:,} rows point at a file that is not on disk. "
            f"Re-run word_tokenizer --updateDatabaseInformation to refresh the paths."]


def dump_schema(conn):
    for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        print(f"Table: {name}")
        print(f"Schema: {sql}\n")


def doctor(db_path=None):
    """Run every check. Returns the number of problems found."""
    db_path = db_path or chunk_database_path
    conn = sqlite3.connect(db_path)

    sections = [
        ("schema drift", check_drift),
        ("orphaned rows", check_orphans),
        ("id scheme", check_id_scheme),
        ("files on disk", check_files_on_disk),
    ]

    print(f"[doctor] {db_path}")
    total = 0
    for label, check in sections:
        try:
            problems = check(conn)
        except sqlite3.Error as exc:
            problems = [f"check failed: {exc}"]

        if problems:
            total += len(problems)
            print(f"\n  {label}:")
            for problem in problems:
                print(f"    ! {problem}")
        else:
            print(f"  {label:<16} ok")

    scheme = conn.execute(
        "SELECT value FROM pipeline_meta WHERE key = 'id_scheme'"
    ).fetchone() if _exists(conn, 'pipeline_meta') else None
    if scheme:
        print(f"\n  id_scheme = {scheme[0]}")

    conn.close()
    print(f"\n[doctor] {total} problem(s) found." if total else "\n[doctor] clean.")
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=chunk_database_path)
    parser.add_argument('--dump', action='store_true', help='print raw DDL and exit')
    args = parser.parse_args()

    if args.dump:
        conn = sqlite3.connect(args.db)
        dump_schema(conn)
        conn.close()
        return 0

    return 1 if doctor(args.db) else 0


if __name__ == '__main__':
    raise SystemExit(main())
