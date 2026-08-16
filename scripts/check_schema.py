import os
import sqlite3
import sys

# Share the pipeline's path resolution instead of pinning an absolute drive path.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
from modules.path import chunk_database_path

try:
    conn = sqlite3.connect(chunk_database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table_name, table_sql in tables:
        print(f"Table: {table_name}")
        print(f"Schema: {table_sql}\n")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
