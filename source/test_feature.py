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
from math import log10
import threading
import time

def batch_collect_words(cursor, batch_size=975, column_name="word", table_name="coverage_analysis") -> Generator[list[str], None, None]:
    offset = 0
    while True:
        cursor.execute(f"SELECT {column_name} FROM {table_name} LIMIT ? OFFSET ?", (batch_size, offset))
        extracted_words = [word[0] for word in cursor.fetchall()]

        if not extracted_words:
            break

        yield extracted_words
        offset += batch_size

def setup_TF_IDF_tables(cursor: sqlite3.Cursor, number_of_tables: int) -> None:
    # Drop all tables
    for index in range(number_of_tables):
        cursor.execute(f"DROP TABLE IF EXISTS TF_IDF_table_{index}")
        print(f"Dropped table TF_IDF_table_{index}")

    # Create tables
    for index, word_list in zip(range(number_of_tables), batch_collect_words(cursor)):
        cursor.execute(f"CREATE TABLE TF_IDF_table_{index} (chunk_text TEXT PRIMARY KEY, FOREIGN KEY(chunk_text) REFERENCES pdf_chunks(chunk_text))")
        cursor.execute(f"INSERT INTO TF_IDF_table_{index} SELECT chunk_text FROM pdf_chunks")
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
    cursor.execute("INSERT INTO TF_IDF_titles SELECT word FROM coverage_analysis")
    title_collection = cursor.execute("SELECT id FROM file_list WHERE chunk_count > 0 AND file_type = 'pdf'").fetchall()
    cleaned_title_collection = [title[0] for title in title_collection]
    for title in cleaned_title_collection:
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_count' INTEGER DEFAULT 0")
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_TF_IDF' REAL DEFAULT 0.0")
    print(f"Created table TF_IDF_titles with {len(cleaned_title_collection)} titles")
    # Complete transaction
    cursor.connection.commit()

def count_a_term_in_a_chunk(term: str, chunk: str, cursor: sqlite3.Cursor, index: int) -> int:
    term_count = chunk.count(term)
    cursor.execute(f"UPDATE TF_IDF_table_{index} SET '{term}_count' = ? WHERE chunk_text = ?", (term_count, chunk))
    return term_count

def compute_TF_IDF(cursor: sqlite3.Cursor, term: str, chunk: str, index: int, term_appearance_count: int, total_words_in_chunk: int, total_document: int, number_document_with_term: int) -> None:
    term_frequency = term_appearance_count / total_words_in_chunk
    document_frequency = total_document / number_document_with_term
    tf_idf_value = term_frequency / log10(1 + document_frequency)
    cursor.execute(f"UPDATE TF_IDF_table_{index} SET '{term}_TF_IDF' = ? WHERE chunk_text = ?", (tf_idf_value, chunk))

def process_in_parallel_TF_IDF(cursor: sqlite3.Cursor, number_of_tables: int) -> None:
    """
    Add in retry mechanism of updating failed
    """
    thread_list = []

    TOTAL_TEXT_CHUNK = cursor.execute("SELECT COUNT(*) FROM pdf_chunks").fetchone()[0]

    for root_word, index in zip(batch_collect_words(cursor), range(number_of_tables)): # For each table
        # First round, count the number of terms appear in a chunk
        for word in root_word:# For each word, count the number of times it appears in the table
            for text_chunk in batch_collect_words(cursor, batch_size= 100, column_name= "chunk_text", table_name= "pdf_chunks"):
                thread = threading.Thread(target=count_a_term_in_a_chunk, args=(word, text_chunk, cursor, index))
                thread.start()
                thread_list.append(thread)
            
            for thread in thread_list:
                thread.join()
        # add a waiting time to finish all threads
        time.sleep(5)
        # Second round, calculate the TF-IDF to gurantee the accuracy
        for word in root_word:
            total_document_with_term = cursor.execute(f"SELECT COUNT(*) FROM TF_IDF_table_{index} WHERE '{word}_count' > 0").fetchone()[0]
            for text_chunk in batch_collect_words(cursor, batch_size= 100, column_name= "chunk_text", table_name= "pdf_chunks"):
                term_appearance_count = cursor.execute(f"SELECT '{word}_count' FROM TF_IDF_table_{index} WHERE chunk_text = ?", (text_chunk,)).fetchone()[0]
                total_words_in_chunk = len(text_chunk.split())
                thread = threading.Thread(target=compute_TF_IDF, args=(cursor,word,text_chunk,index,term_appearance_count,total_words_in_chunk,TOTAL_TEXT_CHUNK,total_document_with_term))
                thread.start()
                thread_list.append(thread)

            for thread in thread_list:
                thread.join()
                
# Main function
def computeTFIDF(database_path: str) -> None:
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    NUMER_OF_WORDS = cursor.execute("SELECT COUNT(*) FROM coverage_analysis").fetchone()[0]
    BATCH_SIZE = 975
    # Round up the number of tables
    number_of_tables = (NUMER_OF_WORDS + BATCH_SIZE - 1) // BATCH_SIZE

    # Setup tables
    setup_TF_IDF_tables(cursor, number_of_tables)
    conn.commit()

    # Count and precompute TF-IDF in multithreaded way
    process_in_parallel_TF_IDF(cursor, number_of_tables)
    conn.commit()

    conn.close()

computeTFIDF(path.chunk_database_path)