import sqlite3
from os.path import getmtime
from datetime import datetime
from modules.path import chunk_database_path
from modules.updateLog import print_and_log
from modules.extract_text import batch_collect_files
from os import basename

def get_modification_time(file_path: str) -> tuple[str, int]:
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
    redundancy &= 0xFFFF

    # Step 4: Combine the results into a unique ID
    unique_id = f"{encoded_file_name:04X}{encoded_time:04X}{encoded_num:04X}{redundancy:04X}"

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
        created_time, epoch_time = get_modification_time(file_path)
        file_basename = basename(file_path)
        chunk_count = count_chunk_for_each_title(cursor, file_name=file_basename)
        starting_id, ending_id = get_starting_and_ending_ids(cursor, file_name=file_basename)
        if starting_id is None or ending_id is None:
            starting_id = 0
            ending_id = 0
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
    return [basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

def create_type_index_table(collector_folder_list: list[str], extension_list: list[str]) -> None:
    print_and_log(f"Started creating file index.")
    
    # Initialize database
    setup_database(reset_db=True, db_name=chunk_database_path)
    
    print_and_log("Started storing files in database.")
    for collector_folder, extension in zip(collector_folder_list, extension_list):
        for file_batch in batch_collect_files(folder_path=collector_folder, extension=extension, batch_size=100):
            file_names = extract_names(file_batch, extension)
            
            for file_name, file_path_with_extension in zip(file_names, file_batch):
                print_and_log(f"Processing file: {file_name}...")
                store_files_in_db(file_names=[file_name], 
                                  file_list=[file_path_with_extension], 
                                  db_name=chunk_database_path, 
                                  file_type=extension.removeprefix("."))

    print_and_log(f"Files: file stored in database.")
    print_and_log(f"Processing complete: create file index.")