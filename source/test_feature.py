"""
Compute TF-IDF scores for each word in each chunk in the PDF file.
1) Create a table with columns: id Foreign key id pdf chunks, word 1 Integer, TF-IDF word 1 Real, word 2, ...
and continue create another table if the columns exceed 1950
2) Create a table with columns: word, title1, title2, ...
3) Do the fucking computation

Phase 2: Prompting and compute relevancy
		1) Setting the rules for prompting.
			- The text has to be at least 200 characters long
		2) Process root words in the prompt and count them
		3) Compute the TF-IDF of the prompt
		4) Multiply them to all TF-IDF values in "title_TF_IDF" 
				'''
				[total impact] = [[title list] : 0]
				[for each root word in the prompt]
					[for each title of that root word]
						[binding value] = [TF-IDF of prompt] * [TF-IDF of title]
						total impact [title] += [binding value]
				'''
		5) Rank for the top 10* of the binding TF-IDF values, *subject to change
		6) For each title, perform step 4 and 5 on the [title]_analysis table and concatenate the top ranking chunk of each title
		7) From concatenate vector, output the top 10* chunk with the corresponding title, chunk ID, and the text chunk, *subject to change

"""

import sqlite3
import modules.path as path
from typing import Generator

def count_one_term_appear_in_each_chunk(term, text_chunk) -> int:
    """
    Count the number of times the term appears in the text chunk.
    """
    text_chunk = text_chunk.lower()
    return text_chunk.count(term.lower())

def batch_collect_words(cursor, batch_size=975) -> Generator[list[str], None, None]:
    offset = 0
    while True:
        cursor.execute("SELECT word FROM coverage_analysis LIMIT ? OFFSET ?", (batch_size, offset))
        extracted_words = [word[0] for word in cursor.fetchall()]

        if not extracted_words:
            break

        yield extracted_words
        offset += batch_size

def setup_tables(cursor: sqlite3.Cursor, number_of_tables: int) -> None:
    # Drop all tables
    for index in range(number_of_tables):
        cursor.execute(f"DROP TABLE IF EXISTS TF_IDF_table_{index}")
        print(f"Dropped table TF_IDF_table_{index}")

    # Create tables
    for index, word_list in zip(range(number_of_tables), batch_collect_words(cursor)):
        cursor.execute(f"CREATE TABLE TF_IDF_table_{index} (word TEXT PRIMARY KEY, FOREIGN KEY(word) REFERENCES coverage_analysis(word))")
        cursor.execute(f"INSERT INTO TF_IDF_table_{index} SELECT word FROM coverage_analysis")
        for keyword in word_list:
            cursor.execute(f"ALTER TABLE TF_IDF_table_{index} ADD COLUMN '{keyword}_count' INTEGER DEFAULT 0")
            cursor.execute(f"ALTER TABLE TF_IDF_table_{index} ADD COLUMN '{keyword}_TF_IDF' REAL DEFAULT 0.0")
        print(f"Created table TF_IDF_table_{index} with {len(word_list)} keywords")

    # Create word_impact_titles table
    cursor.execute("DROP TABLE IF EXISTS TF_IDF_titles")
    print("Dropped table TF_IDF_titles")
    cursor.execute("""CREATE TABLE TF_IDF_titles (
                word TEXT PRIMARY KEY,
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
                )""")
    title_collection = cursor.execute("SELECT id FROM file_list WHERE chunk_count > 0 AND file_type = 'pdf'").fetchall()
    cleaned_title_collection = [title[0] for title in title_collection]
    for title in cleaned_title_collection:
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_count' INTEGER DEFAULT 0")
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_TF_IDF' REAL DEFAULT 0.0")
    print(f"Created table TF_IDF_titles with {len(cleaned_title_collection)} titles")
    # Complete transaction
    cursor.connection.commit()

def compute_tf_idf_text_chunk(database_path: str) -> None:
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    NUMER_OF_WORDS = cursor.execute("SELECT COUNT(*) FROM coverage_analysis").fetchone()[0]
    BATCH_SIZE = 975
    # Round up the number of tables
    number_of_tables = (NUMER_OF_WORDS + BATCH_SIZE - 1) // BATCH_SIZE

    # Setup tables
    setup_tables(cursor, number_of_tables)

compute_tf_idf_text_chunk(path.chunk_database_path)