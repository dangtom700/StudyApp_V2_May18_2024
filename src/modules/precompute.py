import sqlite3
import json
from os import listdir
from os.path import join
from math import sqrt
from concurrent.futures import ThreadPoolExecutor
from modules.path import token_json_path, chunk_database_path
from modules.updateLog import print_and_log
from modules.word_freq import get_title_ids

# Precompute word frequencies for a specific title and insert them into the title_analysis table
def precompute_title_analysis(database_path: str, title_id: str, words: list[str]):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # Load the token counts from the JSON file
    path = join(token_json_path, f"{title_id}.json")
    with open(path, "r", encoding="utf-8") as f:
        tokens = json.load(f)

    # Get word counts for the specified words
    word_counts = {word: tokens.get(word, 0) for word in words}

    # Update the table with the word counts
    for word, count in word_counts.items():
        cursor.execute(f"UPDATE title_analysis SET T_{title_id} = ? WHERE word = ?", (count, word))

    conn.commit()
    conn.close()

# Normalize the word frequencies for a given title (vector normalization)
def normalize_vector(database_path: str, title_id: str):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # Compute the magnitude (length) of the vector for the title
    length = cursor.execute(f"SELECT SUM(T_{title_id} * T_{title_id}) FROM title_analysis").fetchone()[0]
    length = sqrt(length) if length else 1  # Prevent division by zero

    # Update the title_normalized table with normalized values
    cursor.execute(f"""
        UPDATE title_normalized
        SET T_{title_id} = 
            (SELECT T_{title_id} FROM title_analysis WHERE title_normalized.word = title_analysis.word) / ?
    """, (length,))

    conn.commit()
    conn.close()

# Main process to vectorize word frequencies for all titles and normalize them
def vectorize_title(database_path: str):
    conn = sqlite3.connect(database_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL;')

    # Retrieve the list of title IDs from the JSON directory
    pdf_titles = get_title_ids(cursor)

    # Get the list of words from the coverage_analysis table
    words = cursor.execute("SELECT word FROM coverage_analysis").fetchall()
    words = [word[0] for word in words]

    # Function to create and initialize the title_vector and title_normalized tables
    def create_tables(title_ids=pdf_titles):
        integer_columns = ', '.join([f"T_{title_id} INTEGER DEFAULT 0" for title_id in title_ids])
        real_columns = ', '.join([f"T_{title_id} REAL DEFAULT 0.0" for title_id in title_ids])

        # Drop the tables if they already exist
        cursor.execute("DROP TABLE IF EXISTS title_vector")
        cursor.execute("DROP TABLE IF EXISTS title_normalized")

        # Create title_vector table to store raw word frequencies
        cursor.execute(f"""CREATE TABLE title_vector (
            word TEXT PRIMARY KEY,
            {integer_columns})
        """)

        # Create title_normalized table to store normalized frequencies
        cursor.execute(f"""CREATE TABLE title_normalized (
            word TEXT PRIMARY KEY,
            {real_columns})
        """)

        # Populate both tables with words from the coverage_analysis table
        cursor.execute("INSERT INTO title_vector (word) SELECT DISTINCT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_normalized (word) SELECT DISTINCT word FROM coverage_analysis")

    # Log the start of the vectorization process and create necessary tables
    print_and_log("Vectorizing titles...")
    create_tables()
    
    conn.commit()
    conn.close()

    # Use multithreading to speed up the processing of each title
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Precompute word frequencies for each title in parallel
        for title_id in pdf_titles:
            executor.submit(precompute_title_analysis, database_path=database_path, title_id=title_id, words=words)

    # Use multithreading to normalize word frequencies for each title in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        for title_id in pdf_titles:
            executor.submit(normalize_vector, database_path=database_path, title_id=title_id)

    print_and_log("All titles vectorized.")
