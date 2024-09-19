import sqlite3
import time
from modules.path import log_database_path, chunk_database_path
from os import makedirs
from os.path import basename, join, exists
import shutil

def getCurrentTime() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def log_message(message: str, message_type = "PROGRESS") -> None:
    database_name = log_database_path
    current_time = getCurrentTime()
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO messages (timestamp, message_type, message) VALUES (?, ?, ?)", (current_time, message_type ,message))
    conn.commit()
    conn.close()

def store_log_file_to_database(log_file_path: str) -> None:
    database_name = log_database_path
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS messages (timestamp TEXT, message_type TEXT, message TEXT)")
    with open(log_file_path, 'r') as log_file:
        for line in log_file:
            timestamp, message_type, message = line.strip().split(' - ')
            cursor.execute("INSERT INTO messages (timestamp, message_type, message) VALUES (?, ?, ?)", (timestamp, message_type, message))

    cursor.execute("INSERT INTO messages (timestamp, message_type, message) VALUES (?, ?, ?)", (getCurrentTime(), "PROGRESS", "FINISHED UPDATING LOG FILE"))
    conn.commit()
    conn.close()
    # empty_log_file
    with open(log_file_path, 'w') as log_file:
        pass

def print_and_log(message: str, message_type = "PROGRESS") -> None:
    print(message)
    log_message(message, message_type)

def get_time_performance(start_time, message: str) -> None:
    end_time = time.time()
    time_performance = end_time - start_time
    print_and_log(f"{message} took {time_performance} seconds to run.")