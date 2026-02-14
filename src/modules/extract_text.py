import concurrent.futures as cf
import os
import sqlite3
import re

from modules.path import chunk_database_path

# --- Config ---

BATCH_SIZE = 100

# -----------------------------------------------------------------------------------------------
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

    except Exception as e:
        print(f"[ERROR] Failed to process {file}: {e}")

def insert_chunks_into_db(dataset_folder, db_path, overlap_size):
    print("[INFO] Inserting chunks into database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for file in os.listdir(dataset_folder):
        file_path = os.path.join(dataset_folder, file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Prepare data for batch insertion
            data_to_insert = []
            for chunk_id, chunk_text in enumerate(lines):
                chunk_text = chunk_text.strip()
                word_count = len(chunk_text.split())
                
                data_to_insert.append((
                    file, 
                    chunk_id, 
                    chunk_text, 
                    word_count, 
                    overlap_size
                ))

            # Batch execution is significantly faster
            cursor.executemany("""
                INSERT OR IGNORE INTO pdf_chunks 
                (file_name, chunk_id, chunk_text, word_count, overlap_size)
                VALUES (?, ?, ?, ?, ?)
            """, data_to_insert)

        except Exception as e:
            print(f"[ERROR] Failed to insert chunks from {file}: {e}")
        
        os.remove(file_path)

    conn.commit()
    conn.close()
    print("[INFO] Database insertion completed.")

# -----------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------

def extract_text(SOURCE_FOLDER, DEST_FOLDER, CHUNK_SIZE=512, DB_PATH=chunk_database_path):
    """
    Processes .txt files in SOURCE_FOLDER by chunking their text and storing the results
    in a SQLite database at DB_PATH.
    """
    os.makedirs(DEST_FOLDER, exist_ok=True)

    # Step 1: Setup Database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_chunks (
            file_name TEXT,
            chunk_id INTEGER,
            chunk_text TEXT,
            word_count INTEGER,
            overlap_size INTEGER,
            PRIMARY KEY (file_name, chunk_id)
        )
    """)
    conn.commit()

    # Step 2: Process new files
    raw_files = set([f for f in os.listdir(SOURCE_FOLDER) if f.endswith(".txt")])
    zero_byte_files = set([f for f in os.listdir(SOURCE_FOLDER) if os.path.getsize(os.path.join(SOURCE_FOLDER, f)) == 0])
    completed_files = cursor.execute("SELECT DISTINCT file_name FROM pdf_chunks").fetchall()
    completed_files = set([f[0] for f in completed_files])
    new_files = raw_files - completed_files - zero_byte_files
    
    num_raw_files = len(raw_files)
    num_zero = len(zero_byte_files)
    overlap_size = int(CHUNK_SIZE * 0.3)  # Assuming 30% overlap

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
        insert_chunks_into_db(DEST_FOLDER, DB_PATH, overlap_size)

    # Check if all files have been processed
    num_completed = cursor.execute("SELECT COUNT(DISTINCT file_name) FROM pdf_chunks").fetchone()[0]
    print(f"[INFO] {num_completed}/{num_raw_files - num_zero} files processed.")
    conn.close()
