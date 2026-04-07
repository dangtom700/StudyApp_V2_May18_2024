import sqlite3
import sys

try:
    conn = sqlite3.connect('d:/project/StudyApp_V2_May18_2024/data/pdf_text.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    for table_name, table_sql in tables:
        print(f"Table: {table_name}")
        print(f"Schema: {table_sql}\n")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
