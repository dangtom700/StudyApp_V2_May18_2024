"""
data normalization and vector length computation
"""
import sqlite3
import modules.path as path
# from modules.extract_pdf import clean_text
from math import sqrt

# Connect to the database
conn = sqlite3.connect(path.chunk_database_path)
cursor = conn.cursor()

def normalize_vector(title_ids: list[str]) -> None:
    for title in title_ids:
        length = cursor.execute(f"SELECT SUM(title_{title} * title_{title}) FROM title_analysis").fetchone()[0]
        length = sqrt(length)
        cursor.execute(f"""
            UPDATE title_normalized 
                SET title_{title} = 
                    (SELECT title_{title} FROM tile_analysis WHERE title_normalized.word = tile_analysis.word) /(1 + {length})""")
