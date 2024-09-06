import sqlite3
from os import listdir
from math import sqrt
from modules.path import token_json_path, chunk_database_path
from concurrent.futures import ThreadPoolExecutor
from modules.updateLog import print_and_log

def get_title_ids(path:str) -> list[str]:
    return [title.removesuffix(".json") for title in listdir(path)]

def precompute_title_analysis(database_path: str, title_id: str, words: list[str]):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # logic goes here

    conn.commit()
    conn.close()

def normalize_vector(database_path: str, title_id:str):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    length = cursor.execute(f"SELECT SUM(T_{title_id} * T_{title_id}) FROM title_analysis").fetchone()[0]
    length = sqrt(length)
    cursor.execute(f"""
        UPDATE title_normalized
            SET T_{title_id} = 
                (SELECT T_{title_id} FROM title_analysis WHERE title_normalized.word = title_analysis.word) /(1 + {length})
    """)

    conn.commit()
    conn.close()

def vectorize_title(database_path: str): # Main flow
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    title_ids = get_title_ids(path=token_json_path)
    words = cursor.execute("SELECT word FROM coverage_analysis").fetchall()
    words = [word[0] for word in words]

    def create_table(title_ids = title_ids):
        command_fill = ', '.join([f"T_{title_id} INTEGER DEFAULT 0" for title_id in title_ids])
        cursor.execute("DROP TABLE IF EXISTS title_vector")
        cursor.execute(f"""CREATE TABLE title_vector (
            word TEXT PRIMARY KEY,
            {command_fill})
        """)

        cursor.execute("INSERT INTO title_vector (word) SELECT DISTINCT word FROM coverage_analysis")

    print_and_log("Vectorizing titles...")
    create_table(title_ids=title_ids)

    with ThreadPoolExecutor(max_workers=4) as executor:
        for title_id in title_ids:
            print_and_log(f"Vectorizing title {title_id}...")
            executor.submit(precompute_title_analysis, database_path=database_path, title_id=title_id)

    with ThreadPoolExecutor(max_workers=4) as executor:
        for title_id in title_ids:
            print_and_log(f"Normalizing title {title_id}...")
            executor.submit(normalize_vector, database_path=database_path, title_id=title_id)

    print_and_log("All titles vectorized.")
    conn.commit()
    conn.close()

vectorize_title(database_path=chunk_database_path)