"""
Title suggestion system

Phase 1: Precompute the vector length after processing the counting part of popular words
1. Process word frequency analysis, text chunking, and store information in database
2. Create a table with columns: word (from word frequency analysis), title1, title2, ...
3. A map of title and term_count iterate through very word provided by word frequency analysis
4. Store information in database
5. For each title column, compute the vector length of each title

Phase 2: Process prompt for the search
1. Split word and process root word
2. Compute vector length
3. Search for the closest title from the database
"""

import sqlite3
from modules.path import chunk_database_path

def precompute_title_vector(database_name: str) -> None:
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()

    def count_term_in_chunk(chunk: str, term: str):
        return chunk.count(term)
    
    def create_table(title_id: int) -> None:
        cursor.execute("DROP TABLE IF EXISTS Title_Analysis")
        cursor.execute("CREATE TABLE Title_Analysis (word TEXT, FOREIGN KEY(word) REFERENCES coverage_analysis(word))")
        cursor.execute("INSERT INTO Title_Analysis (word) SELECT DISTINCT word FROM coverage_analysis")

        for title in title_id:
            cursor.execute(f"ALTER TABLE Title_Analysis ADD COLUMN '{title}' INTEGER DEFAULT 0")

    def retrive_chunk_and_title_in_batch(bathch_size: int):
        offset = 0
        while True:
            cursor.execute("SELECT file_name, chunk_text FROM pdf_chunks LIMIT ? OFFSET ?", (bathch_size, offset))
            raw_data = cursor.fetchall()
            if not raw_data:
                break

            cleaned_data = list(zip(*raw_data))
            yield raw_data
            offset += bathch_size

    # Main flow
    # Get the needed titles
    cursor.execute("SELECT id, file_name FROM file_list WHERE file_type = 'pdf' AND chunk_count NOT NULL")
    titles = cursor.fetchall()
    title_id = [title[0] for title in titles]
    cleaned_titles = {title[1]: title[0] for title in titles}
    
    # Get the needed words
    cursor.execute("SELECT word FROM coverage_analysis")
    words = cursor.fetchall()
    words = [word[0] for word in words]

    # Create the table
    create_table(title_id= title_id)
    BATCH_SIZE = 100

    for raw_data in retrive_chunk_and_title_in_batch(bathch_size=BATCH_SIZE):
        pass