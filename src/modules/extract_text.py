import concurrent.futures as cf
import os
import sqlite3
import re
import json
import hashlib

from modules import schema
from modules.path import chunk_database_path

# --- Config ---
HASH_NAME_PATTERN = re.compile(r"^[a-f0-9]{64}\.pdf$")
BATCH_SIZE = 100

# Chunking parameters -- the single source of truth for the whole pipeline.
# text_to_chunks splits by WORDS, not characters. modules/catalog.py records these
# as dataset provenance, so keep them here rather than inline at the call site.
DEFAULT_CHUNK_SIZE = 1024      # words per chunk
CHUNK_OVERLAP_RATIO = 0.3      # sliding-window overlap, as a fraction of the chunk size
CHUNK_UNIT = "words"

# The map of content hash -> original filename(s). Written by rename_files, read by
# modules/catalog.py to give every hash-named book a human-readable title.
NAME_MAP_FILE = "_original_names.json"

# -----------------------------------------------------------------------------------------------

"""
From a raw dataset,
1. Refine the text (remove special characters, reduce multiple spaces)
2. Chunk the text into chunks of size chunk_size
3. Create embeddings for each chunk
4. Save text chunks and embeddings to a database
"""

def text_to_chunks(text, chunk_size, overlap=50):
    """
    Split text into chunks of `chunk_size` words with a 
    sliding window of `overlap` words.
    """
    words = text.split()
    chunks = []
    
    # The step is the actual "new" content added to each chunk
    step = chunk_size - overlap
    
    # Ensure we don't get stuck in an infinite loop if overlap >= chunk_size
    if step <= 0:
        step = chunk_size // 2 

    for i in range(0, len(words), step):
        chunk = words[i : i + chunk_size]
        chunks.append(' '.join(chunk))
        
        # Stop if the current chunk reached the end of the word list
        if i + chunk_size >= len(words):
            break
            
    return chunks

def clean_text_for_extracted_data(text):
    """ Only keep A-Z, a-z, 0-9, and spaces. """
    text = re.sub(r'[^A-Za-z0-9\s]', ' ', text) # Replace special chars with space
    return re.sub(r'\s+', ' ', text).strip()    # Collapse multiple spaces into one

def save_chunks_to_file(file_path, chunks):
    """Save each chunk to a new line in a file."""
    with open(file_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(f"{chunk}\n")
        
def process_file(file, source_folder, chunk_size, dataset_folder, overlap_size):
    """Read and chunk a file, saving the output to dataset_folder."""
    if not file.endswith(".txt"):
        return

    try:
        with open(os.path.join(source_folder, file), "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = clean_text_for_extracted_data(raw_text)
        chunks = text_to_chunks(cleaned_text, chunk_size, overlap = overlap_size)

        output_path = os.path.join(dataset_folder, file)
        save_chunks_to_file(output_path, chunks)
        print(f"Complete {file}")

    except Exception as e:
        print(f"[ERROR] Failed to process {file}: {e}")

def insert_chunks_into_db(dataset_folder, db_path):
    print("[INFO] Inserting chunks into database...")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Critical PRAGMA optimizations (huge speed boost)
    cursor.execute("PRAGMA journal_mode = WAL;")        # better concurrency
    cursor.execute("PRAGMA synchronous = OFF;")         # skip fsync (faster, less safe)
    cursor.execute("PRAGMA temp_store = MEMORY;")       # temp tables in RAM
    cursor.execute("PRAGMA cache_size = -100000;")      # ~100MB cache

    try:
        cursor.execute("BEGIN TRANSACTION;")

        for file in os.listdir(dataset_folder):
            file_path = os.path.join(dataset_folder, file)

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data_to_insert = []
                    for chunk_id, line in enumerate(f):
                        chunk_text = line.strip()
                        if not chunk_text:
                            continue

                        data_to_insert.append((
                            file,
                            chunk_id,
                            chunk_text
                        ))

                        # chunked batch insert (prevents huge memory usage)
                        if len(data_to_insert) >= 5000:
                            cursor.executemany("""
                                INSERT OR IGNORE INTO pdf_chunks 
                                (file_name, chunk_id, chunk_text)
                                VALUES (?, ?, ?)
                            """, data_to_insert)
                            data_to_insert.clear()

                    # insert remaining
                    if data_to_insert:
                        cursor.executemany("""
                            INSERT OR IGNORE INTO pdf_chunks 
                            (file_name, chunk_id, chunk_text)
                            VALUES (?, ?, ?)
                        """, data_to_insert)

                os.remove(file_path) # Optional: clean up chunk files after insertion
                print(f"Complete {file_path}")
                conn.commit()

            except Exception as e:
                print(f"[ERROR] Failed on {file}: {e}")

    finally:
        conn.close()

    print("[INFO] Database insertion completed.")

# -----------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------

def extract_text(SOURCE_FOLDER, DEST_FOLDER, CHUNK_SIZE=DEFAULT_CHUNK_SIZE, DB_PATH=chunk_database_path):
    """
    Processes .txt files in SOURCE_FOLDER by chunking their text and storing the results
    in a SQLite database at DB_PATH.
    """
    os.makedirs(DEST_FOLDER, exist_ok=True)

    # Step 1: Setup Database. The DDL for pdf_chunks lives in config/schema.sql --
    # see src/modules/schema.py.
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    schema.apply(conn)

    # Step 2: Process new files
    raw_files = set([f for f in os.listdir(SOURCE_FOLDER) if f.endswith(".txt")])
    zero_byte_files = set([f for f in os.listdir(SOURCE_FOLDER) if os.path.getsize(os.path.join(SOURCE_FOLDER, f)) == 0])
    completed_files = cursor.execute("SELECT DISTINCT file_name FROM pdf_chunks").fetchall()
    completed_files = set([f[0] for f in completed_files])
    new_files = raw_files - completed_files - zero_byte_files
    
    num_raw_files = len(raw_files)
    num_zero = len(zero_byte_files)
    overlap_size = int(CHUNK_SIZE * CHUNK_OVERLAP_RATIO)

    del raw_files
    del zero_byte_files
    del completed_files

    if not new_files:
        print("[INFO] No new files to process.")
    else:
        print(f"[INFO] Found {len(new_files)} new files to process.")

        with cf.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(process_file, f, SOURCE_FOLDER, CHUNK_SIZE, DEST_FOLDER, overlap_size)
                for f in new_files
            ]
            for future in cf.as_completed(futures):
                future.result()  # This will raise exceptions if any occur inside threads

        # Step 3: Insert into database
        insert_chunks_into_db(DEST_FOLDER, DB_PATH)

    # Check if all files have been processed
    num_completed = cursor.execute("SELECT COUNT(DISTINCT file_name) FROM pdf_chunks").fetchone()[0]
    print(f"[INFO] {num_completed}/{num_raw_files - num_zero} files processed.")
    conn.close()

def hash_file_content(path):
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1048576):
            hasher.update(chunk)
    return hasher.hexdigest()

def name_map_path(folder):
    return os.path.join(folder, NAME_MAP_FILE)


def load_name_map(folder):
    """
    Load the {sha256: [original filename, ...]} map.

    A missing map is fine (first run). A *corrupt* map is not: it is the only copy of
    every original filename, so we refuse to continue rather than silently start from
    empty and overwrite it on the way out.
    """
    path = name_map_path(folder)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        raise RuntimeError(
            f"Could not read {path}: {e}\n"
            f"Refusing to overwrite it -- restore from {NAME_MAP_FILE}.bak before re-running."
        ) from e

    # Historical entries are lists; tolerate the odd bare string.
    return {k: (v if isinstance(v, list) else [v]) for k, v in data.items()}


def save_name_map(folder, name_map):
    """Write the map atomically -- a half-written file loses titles permanently."""
    path = name_map_path(folder)
    tmp = path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(name_map, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)


def record_original_name(name_map, file_hash, original_name):
    """Append original_name under file_hash. Returns True if the map changed."""
    names = name_map.setdefault(file_hash, [])
    if original_name in names:
        return False
    names.append(original_name)
    return True


def rename_files(folder):
    """
    Rename every PDF in `folder` to <sha256 of its content>.pdf.

    The original filename is the only human-readable record of what a book is, and
    hashing throws it away -- so it is appended to _original_names.json *before* the
    file is renamed or a duplicate is deleted. That map is what gives modules/catalog.py
    its titles and its download_copies count; if this stops running, title coverage
    decays with every new batch of downloads.
    """
    name_map = load_name_map(folder)
    dirty = False
    renamed = duplicates = 0

    try:
        for file in os.listdir(folder):
            if not file.lower().endswith(".pdf"):
                continue

            if HASH_NAME_PATTERN.match(file):
                continue

            old_path = os.path.join(folder, file)

            try:
                file_hash = hash_file_content(old_path)
                new_name = f"{file_hash}.pdf"
                new_path = os.path.join(folder, new_name)

                # Record first: once the file is renamed or removed below, its original
                # name is unrecoverable. A second entry under the same hash is exactly
                # what makes download_copies > 1 a measured fact.
                dirty |= record_original_name(name_map, file_hash, file)

                if os.path.exists(new_path):
                    print(f"[SKIP] Duplicate detected: {file} -> {new_name}")
                    os.remove(old_path)
                    duplicates += 1
                    continue

                os.rename(old_path, new_path)
                print(f"[RENAMED] {file} -> {new_name}")
                renamed += 1

            except Exception as e:
                print(f"[ERROR] Failed to process {file}: {e}")
    finally:
        # Save whatever was recorded even if the walk above blew up part-way.
        if dirty:
            save_name_map(folder, name_map)

    print(f"[INFO] {renamed} renamed, {duplicates} duplicates removed. "
          f"{NAME_MAP_FILE} holds {len(name_map)} titles.")