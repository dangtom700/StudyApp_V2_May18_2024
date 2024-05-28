import sqlite3
import os
from modules.path import study_notes_folder_path
import time
from modules.updateLog import log_message

def get_note_file_list() -> list[str]:
    return [os.path.join(study_notes_folder_path, file) for file in os.listdir(study_notes_folder_path) if file.endswith(".md")]
def extract_notes_names(raw_list: list[str]) -> list[str]:
    return [file.removesuffix(".md") for file in raw_list if file.endswith(".md")]

def get_created_time_of_file(file_path: str) -> str:
    return time.ctime(os.path.getctime(file_path))

def setup_database(reset_db: bool, db_name: str, action: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    if reset_db:
        cursor.execute("DROP TABLE IF EXISTS note_list")
    cursor.execute("CREATE TABLE note_list (note_name TEXT, file_name TEXT, created_time TEXT)")
    conn.commit()
    conn.close()

def store_notes_in_db(note_names: list[str], file_list: list[str], db_name: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for note_name, file_path in zip(note_names, file_list):
        created_time = get_created_time_of_file(file_path)
        cursor.execute("INSERT INTO note_list (note_name, file_name, created_time) VALUES (?, ?, ?)", (note_name, file_path, created_time))
    conn.commit()
    conn.close()
# Main function
def extract_notes_with_config_path() -> None:
    log_message("Started extracting notes.")
    file_list = get_note_file_list()
    note_names = extract_notes_names(file_list)

    setup_database(reset_db=True, db_name="data\\chunks.db", action="extract_notes")
    log_message("Started storing notes in database.")
    for note_name, file_path in zip(note_names, file_list):
        log_message(f"Processing note: {note_name}...")
        print(f"Processing note: {note_name}...")
        store_notes_in_db(note_names=[note_name], file_list=[file_path], db_name="data\\chunks.db")
    log_message("Notes stored in database.")
    print("Processing complete.")

    
