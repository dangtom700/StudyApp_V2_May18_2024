import sqlite3
import os
from datetime import datetime
from os.path import getmtime
from time import ctime
from modules.updateLog import log_message
from modules.path import chunk_database_path
from modules.extract_pdf import batch_collect_files

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
    cursor.execute(f"CREATE TABLE IF NOT EXISTS {type}_list ({type}_name TEXT, {type}_path TEXT, created_time TEXT)")

    conn.commit()
    conn.close()

def store_files_in_db(file_names: list[str], file_list: list[str], db_name: str, type: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for file_name, file_path in zip(file_names, file_list):
        created_time = get_updated_time(file_path)
        cursor.execute(f"INSERT INTO {type}_list ({type}_name, {type}_path, created_time) VALUES (?, ?, ?)", (file_name, file_path, created_time))
    conn.commit()
    conn.close()
# Main function
def extract_names(raw_list: list[str], extension: str) -> list[str]:
    return [os.path.basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

def create_type_index_table(file_path: str, extension: str, type: str) -> None:
    log_message(f"Started creating {type} index.")
    
    # Initialize database
    setup_database(reset_db=True, db_name=chunk_database_path, type=type)
    
    log_message("Started storing files in database.")
    
    for file_batch in batch_collect_files(file_path=file_path, extension=extension, batch_size=100):
        file_names = extract_names(file_batch, extension)
        
        for file_name, file_path in zip(file_names, file_batch):
            log_message(f"Processing {type}: {file_name}...")
            store_files_in_db(file_names=[file_name], file_list=[file_path], db_name=chunk_database_path, type=type)

    log_message(f"Files: {type} stored in database.")
    print(f"Processing complete: create {type} index.")
