"""
One-time migration: re-key the pipeline onto content-addressed document ids.

Why
---
`file_info.id` was md5 of each PDF's ABSOLUTE PATH (create_unique_id in
src/lib/updateDB.hpp). Every derived table joins through `'title_' || id`, so
moving the library or editing READING_LIST_PATH re-keyed file_info and orphaned
every derived row with no error -- the hazard documented in
docs/CATALOG_DATASET_PLAN.md and the reason --compressPDF must rewrite each file
at its own path.

The stem is already the sha256 of the file's contents, so the id is now
md5(stem): content-derived, path-independent, and still 32 hex characters, so
every `title_<id>` value keeps its shape and no consumer changes.

This script rewrites the existing data to match. Run it once, after building the
binary that contains the new create_unique_id.

What it touches
---------------
    file_info.id
    file_token.file_name
    relation_distance_filtered.file_name
    comparison.source_id, comparison.target_id
    item_matrix.source_id, item_matrix.target_id
    tags.ID
    tags_full.ID
    book_catalog.title_id
    data/token_json/title_<id>.json      (filenames)
    data/low_similarity.txt              (contents)

The JSON renames are not optional: --computeRelationalDistance takes file_name
straight from each JSON file's stem, and skim_files resumes off it. Migrating the
database alone would make the next run reprocess the whole corpus under the old
keys.

Usage
-----
    python scripts/migrate_ids.py --dry-run          # report, change nothing
    python scripts/migrate_ids.py --db data/copy.db --skip-files   # rehearse
    python scripts/migrate_ids.py                    # do it

Take a snapshot first:  sqlite3 data/pdf_text.db "VACUUM INTO 'data/backup.db'"
"""

import argparse
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

import sqlite3
from modules import schema
from modules.path import chunk_database_path, data_folder, token_json_path

# Tables keyed by 'title_' || file_info.id, and which of their columns hold it.
# Each is rebuilt rather than updated in place: these are WITHOUT ROWID tables
# whose primary key is the column being rewritten, and an in-place UPDATE walks
# rows one at a time through states where a new key could collide with an old one
# not yet rewritten.
KEYED_TABLES = {
    'file_token':                 ['file_name'],
    'relation_distance_filtered': ['file_name'],
    'comparison':                 ['source_id', 'target_id'],
    'item_matrix':                ['source_id', 'target_id'],
    'tags':                       ['ID'],
    'tags_full':                  ['ID'],
}

LOW_SIMILARITY = os.path.join(data_folder, 'low_similarity.txt')


def new_id(stem):
    """
    The id src/lib/updateDB.hpp now derives for a file.

    md5 over the UTF-8 bytes of the stem, lowercase hex -- verified to match the
    C++ EVP_md5 path byte for byte. If one side changes, both must.
    """
    return hashlib.md5(stem.encode('utf-8')).hexdigest()


def build_map(conn):
    """old 'title_<id>' -> new 'title_<id>', plus the bare id pairs for file_info."""
    pairs = [(old_id, new_id(stem))
             for old_id, stem in conn.execute("SELECT id, file_name FROM file_info")]

    collisions = len(pairs) - len({n for _, n in pairs})
    if collisions:
        raise SystemExit(f"[migrate] ABORT: {collisions} stems hash to a shared id.")

    return pairs


def already_migrated(conn):
    """
    True when this database is already on content-addressed ids.

    Checks the recorded scheme first, then falls back to recomputing one row --
    a database migrated before pipeline_meta existed still reads correctly.
    """
    try:
        row = conn.execute(
            "SELECT value FROM pipeline_meta WHERE key = 'id_scheme'").fetchone()
        if row and row[0] == 'content-md5':
            return True
    except sqlite3.OperationalError:
        pass

    row = conn.execute("SELECT id, file_name FROM file_info LIMIT 1").fetchone()
    return bool(row) and row[0] == new_id(row[1])


def check_orphans(conn):
    """Rows whose key is not in file_info -- already-broken data, counted per table."""
    found = {}
    for table, columns in KEYED_TABLES.items():
        where = " OR ".join(f'"{c}" NOT IN (SELECT old_key FROM _id_map)' for c in columns)
        n = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE {where}').fetchone()[0]
        if n:
            found[table] = n
    return found


def rekey_tables(conn, drop_orphans):
    """Rebuild every keyed table with its ids rewritten through _id_map."""
    # Move the originals aside, drop the indexes that followed them, then let
    # config/schema.sql recreate the real tables -- the same DDL the pipeline uses,
    # so the migration cannot invent a different shape.
    for table in KEYED_TABLES:
        conn.execute(f'ALTER TABLE "{table}" RENAME TO "{table}__old"')

    stale_indexes = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%' "
        "AND tbl_name LIKE '%__old'")]
    for index in stale_indexes:
        conn.execute(f'DROP INDEX IF EXISTS "{index}"')

    schema.apply(conn, commit=False)

    for table, key_columns in KEYED_TABLES.items():
        columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')]

        selects, joins = [], []
        for position, column in enumerate(columns):
            if column in key_columns:
                alias = f"m{position}"
                selects.append(f'{alias}.new_key')
                joins.append(f'JOIN _id_map {alias} ON {alias}.old_key = o."{column}"')
            else:
                selects.append(f'o."{column}"')

        # An inner join is what discards orphans: a row whose id is not in _id_map has
        # no new key to move to. check_orphans() has already refused to get here unless
        # the caller asked for that.
        column_list = ", ".join(f'"{c}"' for c in columns)
        conn.execute(f'INSERT INTO "{table}" ({column_list}) '
                     f'SELECT {", ".join(selects)} FROM "{table}__old" o {" ".join(joins)}')

        moved = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        before = conn.execute(f'SELECT COUNT(*) FROM "{table}__old"').fetchone()[0]
        print(f"  {table:<28} {before:>9,} -> {moved:>9,}"
              + ("" if moved == before else f"   ({before - moved:,} orphans dropped)"))
        conn.execute(f'DROP TABLE "{table}__old"')

    # file_info.id is a plain UNIQUE column, not a primary key, so it updates in place.
    conn.execute("""
        UPDATE file_info
           SET id = (SELECT substr(new_key, 7) FROM _id_map
                      WHERE old_key = 'title_' || file_info.id)
         WHERE 'title_' || id IN (SELECT old_key FROM _id_map)
    """)

    # book_catalog is rebuilt by --buildCatalog anyway; keeping it consistent here
    # means --catalogStats reports the truth before that next rebuild.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='book_catalog'").fetchone():
        conn.execute("""
            UPDATE book_catalog
               SET title_id = (SELECT new_key FROM _id_map WHERE old_key = book_catalog.title_id)
             WHERE title_id IN (SELECT old_key FROM _id_map)
        """)


def rename_json_files(mapping, folder, dry_run):
    """
    title_<old>.json -> title_<new>.json.

    Two passes through a temporary suffix: old and new names come from the same
    namespace, so a direct rename could land on a file not yet renamed.
    """
    renamed = missing = 0
    staged = []

    for old, new in mapping:
        source = os.path.join(folder, f"title_{old}.json")
        if not os.path.exists(source):
            missing += 1
            continue
        if old == new:
            continue
        if not dry_run:
            temporary = source + ".migrating"
            os.replace(source, temporary)
            staged.append((temporary, os.path.join(folder, f"title_{new}.json")))
        renamed += 1

    for temporary, destination in staged:
        os.replace(temporary, destination)

    return renamed, missing


def rewrite_low_similarity(mapping, dry_run):
    """data/low_similarity.txt lists title_ ids of files with no matches to record."""
    if not os.path.exists(LOW_SIMILARITY):
        return 0

    lookup = {f"title_{old}": f"title_{new}" for old, new in mapping}
    with open(LOW_SIMILARITY, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    rewritten = [lookup.get(line, line) for line in lines]
    changed = sum(1 for a, b in zip(lines, rewritten) if a != b)

    if changed and not dry_run:
        with open(LOW_SIMILARITY, 'w', encoding='utf-8') as f:
            f.write("\n".join(rewritten) + "\n")

    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db', default=chunk_database_path, help='database to migrate')
    parser.add_argument('--json-dir', default=token_json_path, help='token_json folder')
    parser.add_argument('--dry-run', action='store_true', help='report, change nothing')
    parser.add_argument('--skip-files', action='store_true',
                        help='migrate the database only, leaving token_json alone '
                             '(for rehearsing against a copy)')
    parser.add_argument('--drop-orphans', action='store_true',
                        help='discard derived rows whose id has no file_info row '
                             'instead of refusing to run')
    args = parser.parse_args()

    started = time.time()
    conn = sqlite3.connect(args.db)
    # Autocommit: the driver would otherwise open a transaction of its own on the
    # first INSERT, and the explicit BEGIN below would fail inside it.
    conn.isolation_level = None
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-400000")

    if already_migrated(conn):
        print("[migrate] already on content-addressed ids; nothing to do.")
        return 0

    mapping = build_map(conn)
    print(f"[migrate] {len(mapping):,} documents in file_info")

    conn.execute("CREATE TEMP TABLE _id_map (old_key TEXT PRIMARY KEY, new_key TEXT NOT NULL)")
    conn.executemany("INSERT INTO _id_map VALUES (?, ?)",
                     [(f"title_{old}", f"title_{new}") for old, new in mapping])

    orphans = check_orphans(conn)
    if orphans:
        print("[migrate] rows whose id has no file_info row:")
        for table, n in orphans.items():
            print(f"    {table}: {n:,}")
        if not args.drop_orphans:
            print("[migrate] ABORT: these rows cannot be re-keyed. They are already\n"
                  "          unjoinable; re-run with --drop-orphans to discard them.")
            return 1

    if args.dry_run:
        sample = mapping[:3]
        print("[migrate] dry run -- nothing written. Sample of the re-key:")
        for old, new in sample:
            print(f"    title_{old} -> title_{new}")
        renamed, missing = rename_json_files(mapping, args.json_dir, dry_run=True)
        print(f"[migrate] would rename {renamed:,} JSON files ({missing:,} absent)")
        print(f"[migrate] would rewrite {rewrite_low_similarity(mapping, dry_run=True):,} "
              f"low_similarity entries")
        return 0

    print("[migrate] rebuilding keyed tables...")
    conn.execute("BEGIN")
    rekey_tables(conn, args.drop_orphans)
    conn.execute("INSERT INTO pipeline_meta (key, value) VALUES ('id_scheme', 'content-md5') "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value")
    conn.execute("INSERT INTO pipeline_meta (key, value) VALUES ('schema_version', '1') "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value")
    conn.execute("COMMIT")
    print(f"[migrate] database re-keyed in {time.time() - started:.0f}s")

    if args.skip_files:
        print("[migrate] --skip-files: token_json and low_similarity.txt left untouched.")
    else:
        renamed, missing = rename_json_files(mapping, args.json_dir, dry_run=False)
        print(f"[migrate] renamed {renamed:,} JSON files ({missing:,} absent)")
        print(f"[migrate] rewrote {rewrite_low_similarity(mapping, dry_run=False):,} "
              f"low_similarity entries")

    conn.close()
    print(f"[migrate] done in {time.time() - started:.0f}s. "
          f"Run `python src/main.py --dbDoctor` to confirm.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
