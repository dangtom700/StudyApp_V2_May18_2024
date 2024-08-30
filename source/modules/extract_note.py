import sqlite3
import os
import threading
import markdown
import re
import time
from datetime import datetime
from collections.abc import Generator
from os.path import getmtime
from modules.updateLog import print_and_log, log_message
from modules.path import chunk_database_path
from modules.extract_pdf import batch_collect_files, store_chunks_in_db

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

def create_unique_id(file_basename: str, epoch_time: int, chunk_count: int, starting_id: int) -> str:
    # Step 1: Encode the file basename
    # Sum the ASCII values of all characters, XOR by 1600, and apply & 0xFFFF
    encoded_file_name = sum(ord(char) for char in file_basename)
    encoded_file_name ^= 65536
    encoded_file_name &= 0xFFFF

    # Step 2: Encode the epoch time
    # Apply & 0xFFFF, then shift right by 1
    encoded_time = (epoch_time & 0xFFFF) >> 1

    # Step 3: Encode the chunk count and starting ID
    # Multiply, apply & 0xFFFF, then shift left by 1
    encoded_num = (chunk_count * starting_id) & 0xFFFF
    encoded_num <<= 1

    # Step 4: Add redundancy bits
    redundancy = encoded_file_name ^ encoded_time ^ encoded_num

    # Step 4: Combine the results into a unique ID
    unique_id = f"{encoded_file_name:04X}{encoded_time:04X}{encoded_num:05X}{redundancy:04X}"

    return unique_id

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
        created_time, epoch_time = get_updated_time(file_path)
        string_data = file_name + created_time + file_path
        file_basename = os.path.basename(file_path)
        chunk_count = count_chunk_for_each_title(cursor, file_name=file_basename)
        starting_id, ending_id = get_starting_and_ending_ids(cursor, file_name=file_basename)
        hashed_data = create_unique_id(file_basename, epoch_time, chunk_count, starting_id)
        
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
    print_and_log(f"Started creating file index.")
    
    # Initialize database
    setup_database(reset_db=True, db_name=chunk_database_path)
    
    print_and_log("Started storing files in database.")
    for collector_folder, extension in zip(collector_folder_list, extension_list):
        for file_batch in batch_collect_files(folder_path=collector_folder, extension=extension, batch_size=100):
            file_names = extract_names(file_batch, extension)
            
            for file_name, file_path_with_extension in zip(file_names, file_batch):
                log_message(f"Processing file: {file_name}...")
                store_files_in_db(file_names=[file_name], 
                                  file_list=[file_path_with_extension], 
                                  db_name=chunk_database_path, 
                                  file_type=extension.removeprefix("."))

    print_and_log(f"Files: file stored in database.")
    print_and_log(f"Processing complete: create file index.")

def extract_note_text_chunk(file, chunk_size=4000) -> Generator[str, None, None]:
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
        print_and_log(f"Finished processing batch of {len(file_batch)} markdown files.")

    print_and_log("Finished processing markdown files.")
