import sqlite3
import os
import threading
import markdown
import re
import time
import zlib
import base64
from datetime import datetime
from os.path import getmtime
from time import ctime
from modules.updateLog import log_message
from modules.path import chunk_database_path
from modules.extract_pdf import batch_collect_files, store_chunks_in_db
from typing import Generator

def get_updated_time(file_path: str) -> tuple[str, int]:
    # Get the modification time in seconds since EPOCH
    modification_time = getmtime(file_path)
    # Convert the modification time to a recognizable timestamp
    formatted_modification_time = datetime.fromtimestamp(modification_time).strftime('%a, %b %d, %Y, %H:%M:%S')
    epoch_time = int(modification_time)
    return (formatted_modification_time, epoch_time)

def setup_database(reset_db: bool, db_name: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    if reset_db:
        cursor.execute(f"DROP TABLE IF EXISTS file_list")
    cursor.execute(f"""CREATE TABLE IF NOT EXISTS file_list (
                   id TEXT PRIMARY KEY, 
                   file_name TEXT, 
                   file_path TEXT, 
                   file_type TEXT,
                   created_time TEXT, 
                   epoch_time INTEGER,
                   chunk_count INTEGER,
                   start_id INTEGER,
                   end_id INTEGER
                   )""")

    conn.commit()
    conn.close()

def create_unique_id(data: str) -> str:
    # Generate a CRC32 hash
    crc32_hash = zlib.crc32(data.encode())
    
    # Convert to base64 and trim to 16 characters
    base64_id = base64.urlsafe_b64encode(crc32_hash.to_bytes(4, byteorder='big')).decode()[:16]
    
    return base64_id

def count_chunk_for_each_title(cursor: sqlite3.Cursor, file_name: str) -> int:
    cursor.execute(f"SELECT COUNT(chunk_index) FROM pdf_chunks WHERE file_name = ?", (file_name,))
    chunk_count = cursor.fetchone()[0]
    # print(f"Chunk count for {file_name}: {chunk_count}")
    return chunk_count

def get_starting_and_ending_ids(cursor: sqlite3.Cursor, file_name: str) -> tuple[int, int]:
    # Execute a single query to get both the starting and ending IDs
    cursor.execute('''
        SELECT MIN(id) AS starting_id, MAX(id) AS ending_id
        FROM pdf_chunks
        WHERE file_name = ?;
    ''', (file_name,))
    
    result = cursor.fetchone()
    
    starting_id, ending_id = result
    # print(f"Starting ID: {starting_id}, Ending ID: {ending_id}")
    return starting_id, ending_id

def store_files_in_db(file_names: list[str], file_list: list[str], db_name: str, file_type: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for file_name, file_path in zip(file_names, file_list):
        epoch_time, created_time = get_updated_time(file_path)
        string_data = file_name + created_time + file_path
        file_basename = os.path.basename(file_path)
        chunk_count = count_chunk_for_each_title(cursor, file_name=file_basename)
        starting_id, ending_id = get_starting_and_ending_ids(cursor, file_name=file_basename)
        hashed_data = create_unique_id(string_data)
        
        cursor.execute(f"""INSERT INTO file_list (
            id, 
            file_name, 
            file_path,
            file_type,
            created_time,
            epoch_time,
            chunk_count,
            start_id,
            end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (hashed_data, file_name, file_path, file_type, created_time, epoch_time, chunk_count, starting_id, ending_id)
        )
    conn.commit()
    conn.close()
# Main function
def extract_names(raw_list: list[str], extension: list[str]) -> list[str]:
    return [os.path.basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

def create_type_index_table(collector_folder_list: list[str], extension_list: list[str]) -> None:
    log_message(f"Started creating file index.")
    
    # Initialize database
    setup_database(reset_db=True, db_name=chunk_database_path)
    
    log_message("Started storing files in database.")
    for collector_folder, extension in zip(collector_folder_list, extension_list):
        for file_batch in batch_collect_files(folder_path=collector_folder, extension=extension, batch_size=100):
            file_names = extract_names(file_batch, extension)
            
            for file_name, file_path_with_extension in zip(file_names, file_batch):
                log_message(f"Processing file: {file_name}...")
                store_files_in_db(file_names=[file_name], 
                                  file_list=[file_path_with_extension], 
                                  db_name=chunk_database_path, 
                                  file_type=extension.removeprefix("."))

    log_message(f"Files: file stored in database.")
    print(f"Processing complete: create file index.")

def extract_note_text_chunk(file, chunk_size=8000):
    """Extracts and cleans text chunk by chunk from a markdown file."""
    content = []
    for line in file:
        content.append(line)
        if sum(len(c) for c in content) >= chunk_size:
            yield ''.join(content)
            content = []
    
    if content:
        yield ''.join(content)

def clean_markdown_text(markdown_text) -> str:
    """Converts markdown text to plain text by removing HTML tags."""
    html_content = markdown.markdown(markdown_text)
    text = re.sub(r'<[^>]+>', '', html_content)
    return text

def store_text_note_in_chunks_with_retry(file_name, chunks, db_name, MAX_RETRIES = 999, RETRY_DELAY = 10) -> None:
    """Stores chunks in the database with retry logic."""
    attempts = 0
    while attempts < MAX_RETRIES:
        try:
            store_chunks_in_db(file_name=file_name, chunks=chunks, db_name=db_name)
            break  # If successful, break out of the loop
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                attempts += 1
                time.sleep(RETRY_DELAY)
                continue
            else:
                raise  # Raise other SQLite exceptions
        except Exception as e:
            print(f"Error while storing chunks: {e}")
            raise  # Raise any other exceptions
    else:
        print(f"Failed to store chunks after {MAX_RETRIES} attempts for file {file_name}")

def process_markdown_file(file_path, CHUNK_SIZE = 800) -> None:
    """Processes a single markdown file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        for raw_chunk in extract_note_text_chunk(file):
            text = clean_markdown_text(raw_chunk)
            chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
            store_text_note_in_chunks_with_retry(file_name=os.path.basename(file_path), chunks=chunks, db_name=chunk_database_path)

def process_text_note_batch_of_files(file_batch: list[str], chunk_size = 800) -> None:
    """Processes a batch of markdown files concurrently."""
    threads = []
    
    for file_path in file_batch:
        thread = threading.Thread(target=process_markdown_file, args=(file_path,chunk_size,))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()  # Wait for all threads in the batch to finish

def extract_markdown_notes_in_batches(directory, chunk_size = 800) -> None:
    """Main process to collect, extract, chunk, and store markdown files in batches using multithreading."""
    for file_batch in batch_collect_files(folder_path=directory, extension='.md'):
        process_text_note_batch_of_files(file_batch, chunk_size=chunk_size)
        print(f"Finished processing batch of {len(file_batch)} markdown files.")
        log_message(f"Finished processing batch of {len(file_batch)} markdown files.")

    print("Finished processing markdown files.")
    log_message("Finished processing markdown files.")

def batch_collect_words(cursor, batch_size=975) -> Generator[list[str], None, None]:
    offset = 0
    while True:
        cursor.execute("SELECT word FROM coverage_analysis LIMIT ? OFFSET ?", (batch_size, offset))
        extracted_words = [word[0] for word in cursor.fetchall()]

        if not extracted_words:
            break

        yield extracted_words
        offset += batch_size

def setup_tables(cursor: sqlite3.Cursor, number_of_tables: int) -> None:
    # Drop all tables
    for index in range(number_of_tables):
        cursor.execute(f"DROP TABLE IF EXISTS IF_IDF_table_{index}")
        print(f"Dropped table IF_IDF_table_{index}")
        log_message(f"Dropped table IF_IDF_table_{index}")

    # Create tables
    for index, word_list in zip(range(number_of_tables), batch_collect_words(cursor)):
        cursor.execute(f"CREATE TABLE IF_IDF_table_{index} (word TEXT PRIMARY KEY, FOREIGN KEY(word) REFERENCES coverage_analysis(word))")
        cursor.execute(f"INSERT INTO IF_IDF_table_{index} SELECT word FROM coverage_analysis")
        for keyword in word_list:
            cursor.execute(f"ALTER TABLE IF_IDF_table_{index} ADD COLUMN '{keyword}_count' INTEGER DEFAULT 0")
            cursor.execute(f"ALTER TABLE IF_IDF_table_{index} ADD COLUMN '{keyword}_TF_IDF' REAL DEFAULT 0.0")
        print(f"Created table IF_IDF_table_{index} with {len(word_list)} keywords")
        log_message(f"Created table IF_IDF_table_{index} with {len(word_list)} keywords")

    # Create word_impact_titles table
    cursor.execute("DROP TABLE IF EXISTS TF_IDF_titles")
    print("Dropped table TF_IDF_titles")
    log_message("Dropped table TF_IDF_titles")
    cursor.execute("""CREATE TABLE TF_IDF_titles (
                word TEXT PRIMARY KEY,
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
                )""")
    title_collection = cursor.execute("SELECT id FROM file_list WHERE chunk_count > 0 AND file_type = 'pdf'").fetchall()
    cleaned_title_collection = [title[0] for title in title_collection]
    for title in cleaned_title_collection:
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_count' INTEGER DEFAULT 0")
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_TF_IDF' REAL DEFAULT 0.0")
    print(f"Created table TF_IDF_titles with {len(cleaned_title_collection)} titles")
    log_message(f"Created table TF_IDF_titles with {len(cleaned_title_collection)} titles")
    # Complete transaction
    cursor.connection.commit()

def compute_tf_idf_text_chunk(database_path: str) -> None:
    pass