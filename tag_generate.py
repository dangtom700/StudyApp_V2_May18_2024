import json
import sqlite3
from pathlib import Path
from typing import List, Tuple

# =========================================================
# Configuration
# =========================================================

CONFIG = {
    "DB_PATH": Path("data/pdf_text.db"),
    "JSON_PATH": Path("data/base_cases.json"),
    "SOURCE_FOLDER": Path("D:/READING LIST"),
    "NOTES_FOLDER_NAME": "notes",
    "DISTANCE_THRESHOLD": 0.5,
    "DEGREE_THRESHOLDS": {
        2: 0.8
        # 3: 0.6
    },
    "RECOMMEND_LIMIT": 150,
    "CHUNK_SAMPLE_SIZE": 3,
    "BATCH_SIZE": 200_000
}

CONFIG["DESTINATION_FOLDER"] = CONFIG["SOURCE_FOLDER"] / CONFIG["NOTES_FOLDER_NAME"]

# =========================================================
# Utility: Database Context
# =========================================================

def get_connection():
    conn = sqlite3.connect(CONFIG["DB_PATH"])
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# =========================================================
# Filter item_matrix → item_matrix_filtered (Chunked)
# =========================================================

def prepare_filtered_table(reset=True):
    with get_connection() as db:

        if reset:
            db.execute("DROP TABLE IF EXISTS item_matrix_filtered;")

        db.execute("PRAGMA journal_mode=WAL;")
        db.execute("PRAGMA synchronous=NORMAL;")

        db.execute("""
            CREATE TABLE IF NOT EXISTS item_matrix_filtered (
                source_name TEXT NOT NULL,
                target_name TEXT NOT NULL,
                distance REAL NOT NULL,
                PRIMARY KEY (source_name, target_name)
            );
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_imf_source_distance
            ON item_matrix_filtered(source_name, distance DESC);
        """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_imf_target_distance
            ON item_matrix_filtered(target_name, distance DESC);
        """)

        last_rowid = 0

        while True:
            rows = db.execute(
                """
                SELECT rowid, source_name, target_name, distance
                FROM item_matrix
                WHERE rowid > ?
                  AND distance > ?
                ORDER BY rowid
                LIMIT ?;
                """,
                (last_rowid, CONFIG["DISTANCE_THRESHOLD"], CONFIG["BATCH_SIZE"])
            ).fetchall()

            if not rows:
                break

            db.executemany(
                """
                INSERT OR IGNORE INTO item_matrix_filtered
                (source_name, target_name, distance)
                VALUES (?, ?, ?);
                """,
                [(r[1], r[2], r[3]) for r in rows]
            )

            last_rowid = rows[-1][0]
            db.commit()

            print(f"Processed up to rowid {last_rowid}")

    print("Filtered table prepared.")


# =========================================================
# Tag System
# =========================================================

def setup_tags_table(db: sqlite3.Connection):
    db.execute("DROP TABLE IF EXISTS tags;")

    db.execute("""
        CREATE TABLE tags (
            name TEXT NOT NULL,
            tag TEXT NOT NULL,
            degree INTEGER NOT NULL CHECK (degree >= 1),
            PRIMARY KEY (name, tag)
        );
    """)

    db.execute("CREATE INDEX idx_tags_degree ON tags(degree);")

    db.execute("CREATE INDEX IF NOT EXISTS idx_imf_source ON item_matrix_filtered(source_name);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_imf_target ON item_matrix_filtered(target_name);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_imf_distance ON item_matrix_filtered(distance);")


def insert_degree_1(db: sqlite3.Connection, base_data: dict):
    rows = [
        (name, tag, 1)
        for tag, names in base_data.items()
        for name in names
    ]

    db.executemany(
        "INSERT OR IGNORE INTO tags (name, tag, degree) VALUES (?, ?, ?);",
        rows
    )

    print("Degree 1 inserted.")


def expand_degree(db: sqlite3.Connection, from_degree: int, to_degree: int, threshold: float):

    db.execute(
        f"""
        INSERT OR IGNORE INTO tags (name, tag, degree)
        SELECT DISTINCT
            CASE
                WHEN im.source_name = t.name THEN im.target_name
                ELSE im.source_name
            END,
            t.tag,
            {to_degree}
        FROM item_matrix_filtered im
        JOIN tags t
          ON (im.source_name = t.name OR im.target_name = t.name)
        WHERE t.degree = ?
          AND im.distance > ?;
        """,
        (from_degree, threshold)
    )

    print(f"Degree {to_degree} inserted.")


def run_tag_propagation(reset=False):
    with open(CONFIG["JSON_PATH"], "r") as f:
        base_data = json.load(f)

    with get_connection() as db:
        if reset:
            setup_tags_table(db)
        insert_degree_1(db, base_data)

        for degree, threshold in CONFIG["DEGREE_THRESHOLDS"].items():
            expand_degree(db, degree - 1, degree, threshold)

        db.commit()

    print("Tag propagation complete.")


# =========================================================
# File Scanning
# =========================================================

def scan_pdf_files(reset=False) -> List[Path]:
    pdf_files = [
        f for f in CONFIG["SOURCE_FOLDER"].iterdir()
        if f.is_file() and f.suffix.lower() == ".pdf"
    ]

    if reset:
        return pdf_files

    return [
        f for f in pdf_files
        if not (CONFIG["DESTINATION_FOLDER"] / f"BOOK {f.stem}.md").exists()
    ]


# =========================================================
# Recommendation System
# =========================================================

def get_random_chunks(db, filename, limit):
    return db.execute(
        """
        SELECT chunk_id, chunk_text
        FROM pdf_chunks
        WHERE file_name = ?
        ORDER BY RANDOM()
        LIMIT ?;
        """,
        (filename, limit)
    ).fetchall()


def get_recommendations(db, filename, limit, min_distance):
    rows = db.execute(
        """
        SELECT target_name, distance
        FROM item_matrix_filtered
        WHERE source_name = ?
          AND distance > ?

        UNION ALL

        SELECT source_name, distance
        FROM item_matrix_filtered
        WHERE target_name = ?
          AND distance > ?

        ORDER BY distance DESC
        LIMIT ?;
        """,
        (filename, min_distance, filename, min_distance, limit)
    ).fetchall()

    seen = set()
    ranked = []

    for name, distance in rows:
        if name != filename and name not in seen:
            seen.add(name)
            ranked.append((name, distance))

    return ranked


# =========================================================
# Note Generator
# =========================================================

def generate_notes(reset=False):
    CONFIG["DESTINATION_FOLDER"].mkdir(parents=True, exist_ok=True)

    with get_connection() as db:

        pdf_list = scan_pdf_files(reset)
        total = len(pdf_list)

        for pdf_path in pdf_list:
            base_name = pdf_path.stem
            txt_name = f"{base_name}.txt"

            chunks = get_random_chunks(db, txt_name, CONFIG["CHUNK_SAMPLE_SIZE"])
            recommendations = get_recommendations(
                db,
                base_name,
                CONFIG["RECOMMEND_LIMIT"],
                CONFIG["DISTANCE_THRESHOLD"]
            )

            tags = db.execute(
                "SELECT tag FROM tags WHERE name = ?;",
                (base_name,)
            ).fetchall()

            output_path = CONFIG["DESTINATION_FOLDER"] / f"BOOK {base_name}.md"

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# BOOK: {base_name}\n\n")
                f.write(f"Source: [[{pdf_path.name}]]\n\n")

                if tags:
                    f.write("Tags: #" + ", #".join(t[0] for t in tags) + "\n\n")

                for chunk_id, chunk_text in chunks:
                    f.write(f"> {chunk_id}\n> {chunk_text.strip()}\n\n")

                if recommendations:
                    f.write("## Recommended Reading\n\n")
                    f.write("| # | PDF | Notes | Relatability |\n")
                    f.write("|---|-----|-------|--------------|\n")

                    for i, (rec, distance) in enumerate(recommendations, 1):
                        f.write(
                            f"| {i} | [[{rec}.pdf]] | [[BOOK {rec}.md]] | {distance:.4f} |\n"
                        )

                f.write("\n---\n")

    print("Notes generated.")


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    reset = False  # Set to True to reset tables and regenerate all notes

    prepare_filtered_table(reset=reset)
    run_tag_propagation(reset=reset)
    generate_notes(reset=reset)