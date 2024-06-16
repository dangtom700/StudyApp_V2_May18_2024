import sqlite3
import os
from datetime import datetime
from os.path import getmtime
from time import ctime
from modules.updateLog import log_message
from modules.path import pdf_path, study_notes_folder_path, chunk_database_path

def get_file_list(file_path: str, extenstion: str) -> list[str]:
    return [os.path.join(file_path, file) for file in os.listdir(file_path) if file.endswith(extenstion)]
def extract_names(raw_list: list[str], extension: str) -> list[str]:
    return [os.path.basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

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
def create_type_index_table(file_path: str, extenstion: str, type: str) -> None:
    log_message(f"Started creating {type} index.")
    file_list = get_file_list(file_path=file_path, extenstion=extenstion)
    file_names = extract_names(file_list, extenstion)

    setup_database(reset_db=True, db_name=chunk_database_path, type=type)
    log_message("Started storing files in database.")
    for file_name, file_path in zip(file_names, file_list):
        log_message(f"Processing {type}: {file_name}...")
        store_files_in_db(file_names=[file_name], file_list=[file_path], db_name=chunk_database_path, type=type)
    log_message(f"Files: {type} stored in database.")
    print(f"Processing complete: create {type} index.")
