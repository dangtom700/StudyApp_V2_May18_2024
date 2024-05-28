import sqlite3
import os
import time

def getCurrentTime() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
def log_message(message: str) -> None:
    database_name = os.getcwd() + '\\data\\log_message.db'
    current_time = getCurrentTime()
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO messages (timestamp, message_type, message) VALUES (?, ?, ?)", (current_time,"PROGRESS",message))
    conn.commit()
    conn.close()

def store_log_file_to_database(log_file_path: str) -> None:
    database_name = os.getcwd() + '\\data\\log_message.db'
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