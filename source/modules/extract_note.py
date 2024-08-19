import sqlite3
import os
import threading
import markdown
import re
import time
import hashlib
from datetime import datetime
from os.path import getmtime
from time import ctime
from modules.updateLog import log_message
from modules.path import chunk_database_path
from modules.extract_pdf import batch_collect_files
from modules.extract_pdf import batch_collect_files, store_chunks_in_db
from typing import List

def get_updated_time(file_path: str) -> str:
    """
    Given a file path, this function retrieves the modification time of the file and converts it to a recognizable timestamp.

    Parameters:
        file_path (str): The path to the file.

    Returns:
        str: The modification time of the file in the format of '%a, %b %d, %Y, %H:%M:%S'.
    """
    # Get the modification time in seconds since EPOCH
    modification_time = getmtime(file_path)
    # Convert the modification time to a recognizable timestamp
    formatted_modification_time = ctime(modification_time)
    formatted_modification_time = datetime.fromtimestamp(modification_time).strftime('%a, %b %d, %Y, %H:%M:%S')
    return formatted_modification_time

def setup_database(reset_db: bool, db_name: str, type: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    if reset_db:
        cursor.execute(f"DROP TABLE IF EXISTS {type}_list")
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {type}_list (id TEXT PRIMARY KEY, {type}_name TEXT, {type}_path TEXT, created_time TEXT)")

    conn.commit()
    conn.close()

def create_sha256_hash(data: str) -> str:
    # Create SHA-256 hash object
    sha256 = hashlib.sha256()
    # Update hash object with data
    sha256.update(data.encode())
    # Get the hexadecimal digest of the hash
    hex_hash = sha256.hexdigest()
    # Return the first 20 characters of the hex digest
    return hex_hash[:20]

def store_files_in_db(file_names: list[str], file_list: list[str], db_name: str, type: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for file_name, file_path in zip(file_names, file_list):
        created_time = get_updated_time(file_path)
        string_data = file_name + created_time + file_path
        hashed_data = create_sha256_hash(string_data)
        cursor.execute(f"INSERT INTO {type}_list (id, {type}_name, {type}_path, created_time) VALUES (?, ?, ?, ?)", (hashed_data, file_name, file_path, created_time))
    conn.commit()
    conn.close()
# Main function
def extract_names(raw_list: list[str], extension: str) -> list[str]:
    return [os.path.basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

def create_type_index_table(collector_folder: str, extension: str, type: str) -> None:
    log_message(f"Started creating {type} index.")
    
    # Initialize database
    setup_database(reset_db=True, db_name=chunk_database_path, type=type)
    
    log_message("Started storing files in database.")
    
    for file_batch in batch_collect_files(folder_path=collector_folder, extension=extension, batch_size=100):
        file_names = extract_names(file_batch, extension)
        
        for file_name, file_path_with_extension in zip(file_names, file_batch):
            log_message(f"Processing {type}: {file_name}...")
            store_files_in_db(file_names=[file_name], file_list=[file_path_with_extension], db_name=chunk_database_path, type=type)

    log_message(f"Files: {type} stored in database.")
    print(f"Processing complete: create {type} index.")

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

def clean_markdown_text(markdown_text):
    """Converts markdown text to plain text by removing HTML tags."""
    html_content = markdown.markdown(markdown_text)
    text = re.sub(r'<[^>]+>', '', html_content)
    return text

def store_text_note_in_chunks_with_retry(file_name, chunks, db_name, MAX_RETRIES = 999, RETRY_DELAY = 10):
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

def process_markdown_file(file_path, CHUNK_SIZE = 800):
    """Processes a single markdown file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        for raw_chunk in extract_note_text_chunk(file):
            text = clean_markdown_text(raw_chunk)
            chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
            store_text_note_in_chunks_with_retry(file_name=os.path.basename(file_path), chunks=chunks, db_name=chunk_database_path)

def process_text_note_batch_of_files(file_batch: List[str], chunk_size = 800):
    """Processes a batch of markdown files concurrently."""
    threads = []
    
    for file_path in file_batch:
        thread = threading.Thread(target=process_markdown_file, args=(file_path,chunk_size,))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()  # Wait for all threads in the batch to finish

def extract_markdown_notes_in_batches(directory, chunk_size = 800):
    """Main process to collect, extract, chunk, and store markdown files in batches using multithreading."""
    for file_batch in batch_collect_files(folder_path=directory, extension='.md'):
        process_text_note_batch_of_files(file_batch, chunk_size=chunk_size)
        print(f"Finished processing batch of {len(file_batch)} markdown files.")
        log_message(f"Finished processing batch of {len(file_batch)} markdown files.")

    print("Finished processing markdown files.")
    log_message("Finished processing markdown files.")