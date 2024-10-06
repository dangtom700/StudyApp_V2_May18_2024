import sqlite3
import time
from modules.path import log_database_path, chunk_database_path
import datetime

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

def get_time_performance(start_time: datetime.datetime, message: str) -> None:
    end_time = datetime.datetime.now()
    time_diff = end_time - start_time
    print(f"{message} took {time_diff} seconds")