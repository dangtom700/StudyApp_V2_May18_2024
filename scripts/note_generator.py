import os
import sqlite3
import sys

# ======================
# PATH SETUP
# ======================
# Share the pipeline's path resolution so .env (READING_LIST_PATH) is honoured.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from modules.path import chunk_database_path, pdf_path, data_folder

DATA_DIR = data_folder
DB_PATH = chunk_database_path

PDF_FOLDER = pdf_path
NOTE_FOLDER = os.path.join(PDF_FOLDER, "notes")

# ======================
# DB CONNECTION (READ-ONLY + TUNED)
# ======================
conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Performance pragmas (safe in read-only)
cursor.execute("PRAGMA temp_store = MEMORY;")
cursor.execute("PRAGMA cache_size = -200000;")  # ~200MB cache

# ======================
# SQL (NO STRING OPS / NO JOINS)
# ======================

GET_ID_SQL = "SELECT id FROM file_info WHERE file_name = ?"

GET_LABEL_SQL = """
SELECT topic 
FROM tags_full 
WHERE ID = ? 
ORDER BY distance DESC 
LIMIT 20
"""

GET_RECOMMEND_SQL = """
WITH related_ids AS (
    SELECT * FROM (
        SELECT target_id AS other_id, distance
        FROM item_matrix
        WHERE source_id = ?
        ORDER BY distance DESC
        LIMIT 100
    )

    UNION ALL

    SELECT * FROM (
        SELECT source_id AS other_id, distance
        FROM item_matrix
        WHERE target_id = ?
        ORDER BY distance DESC
        LIMIT 100
    )
)
SELECT other_id, distance
FROM related_ids
ORDER BY distance DESC
LIMIT 100;
"""

GET_PREVIEW_SQL = """
SELECT chunk_text 
FROM pdf_chunks 
WHERE file_name = ? 
ORDER BY chunk_id 
LIMIT 1
"""

# ======================
# PRELOAD LOOKUP TABLE (CRITICAL)
# ======================
def load_id_to_filename():
    rows = cursor.execute("SELECT id, file_name FROM file_info").fetchall()
    return {str(row["id"]): row["file_name"] for row in rows}

ID_TO_FILENAME = load_id_to_filename()

# ======================
# HELPERS
# ======================

def extract_numeric_id(raw_id: str) -> str:
    # "title_123" -> "123"
    return raw_id.split("_", 1)[1]


def get_id(filename: str) -> str:
    base_name = os.path.splitext(filename)[0]
    row = cursor.execute(GET_ID_SQL, (base_name,)).fetchone()
    if row is None:
        raise ValueError(f"File not found in DB: {base_name}")
    return f"title_{row['id']}"


def get_labels(source_id: str) -> list[str]:
    rows = cursor.execute(GET_LABEL_SQL, (source_id,)).fetchall()
    return [row["topic"] for row in rows]


def get_recommendations(source_id: str) -> list[str]:
    rows = cursor.execute(GET_RECOMMEND_SQL, (source_id, source_id)).fetchall()

    results = []
    seen = set()

    for row in rows:
        raw_id = row["other_id"]
        numeric_id = extract_numeric_id(raw_id)

        if numeric_id in seen:
            continue
        seen.add(numeric_id)

        filename = ID_TO_FILENAME.get(numeric_id)
        if filename:
            results.append(f"{filename}.md")

    return results


def get_summary_preview(filename: str) -> str:
    row = cursor.execute(GET_PREVIEW_SQL, (filename + ".txt",)).fetchone()
    if row and row["chunk_text"]:
        text = row["chunk_text"].strip()
        return text[:1500] + "..." if len(text) > 1500 else text
    return "No preview available."


# ======================
# FILE PROCESSING
# ======================

os.makedirs(NOTE_FOLDER, exist_ok=True)

processed_files = set(os.listdir(NOTE_FOLDER))
all_pdfs = [f for f in os.listdir(PDF_FOLDER) if f.lower().endswith(".pdf")]

processing_files = [
    f for f in all_pdfs
    if os.path.splitext(f)[0] + ".md" not in processed_files
]

total = len(all_pdfs)
remaining = len(processing_files)
processed = total - remaining

print(f"Resuming: {processed}/{total} files already processed.")
print(f"To process: {remaining} files.\n")

# ======================
# MAIN LOOP
# ======================

for file_index, filename in enumerate(processing_files, start=1):

    try:
        source_id = get_id(filename)
    except ValueError as e:
        print(f"Skipping {filename}: {e}")
        continue

    note_name = os.path.splitext(filename)[0] + ".md"
    note_path = os.path.join(NOTE_FOLDER, note_name)

    labels = get_labels(source_id)
    recommendations = get_recommendations(source_id)
    if not recommendations:
        print(f"Warning: No recommendations found for {filename} (ID: {source_id})")
        continue

    with open(note_path, "w", encoding="utf-8") as f:
        title = os.path.splitext(filename)[0]

        f.write(f"# {title}\n\n")
        f.write(f"Source: [[{filename}]]\n\n")

        f.write("> This is an auto-generated note based on content extracted from the PDF. It may contain errors or omissions. Please verify with the original source.\n\n")

        if labels:
            f.write(f"Labels: #{', #'.join(labels)}\n\n")
        else:
            f.write("Labels: #untagged\n\n")

        f.write("### Recommended for further reading:\n\n")

        if recommendations:
            for rec_index, rec in enumerate(recommendations, start=1):
                f.write(f"{rec_index}. [[{rec}]]\n")
        else:
            f.write("No recommendations found.\n")

    print(
        f"{file_index}/{remaining} "
        f"({file_index/remaining:.2%}) "
        f"Processed: {filename} -> {note_name}"
    )

conn.close()