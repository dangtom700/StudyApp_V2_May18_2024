"""
Compute TF-IDF scores for each word in each chunk in the PDF file.
1) Create a table with columns: id Foreign key id pdf chunks, word 1 Integer, TF-IDF word 1 Real, word 2, ...
and continue create another table if the columns exceed 1950
2) Create a table with columns: word, title1, title2, ...
3) Do the fucking computation
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
    for index in range(number_of_tables):
        cursor.execute(f"DROP TABLE IF EXISTS TF_IDF_table_{index}")
        cursor.execute(f"""
            CREATE TABLE TF_IDF_table_{index} (
                chunk_text TEXT,
                FOREIGN KEY(chunk_text) REFERENCES pdf_chunks(chunk_text)
            )
        """)
        cursor.execute(f"INSERT INTO TF_IDF_table_{index} (chunk_text) SELECT chunk_text FROM pdf_chunks")
        word_list = next(batch_collect_words(cursor))
        for keyword in word_list:
            cursor.execute(f"ALTER TABLE TF_IDF_table_{index} ADD COLUMN '{keyword}_count' INTEGER DEFAULT 0")
            cursor.execute(f"ALTER TABLE TF_IDF_table_{index} ADD COLUMN '{keyword}_TF_IDF' REAL DEFAULT 0.0")

    cursor.execute("DROP TABLE IF EXISTS TF_IDF_titles")
    cursor.execute("""
        CREATE TABLE TF_IDF_titles (
            word TEXT PRIMARY KEY,
            FOREIGN KEY(word) REFERENCES coverage_analysis(word)
        )
    """)
    cursor.execute("INSERT INTO TF_IDF_titles (word) SELECT DISTINCT word FROM coverage_analysis")
    title_collection = cursor.execute("SELECT id FROM file_list WHERE chunk_count > 0 AND file_type = 'pdf'").fetchall()
    cleaned_title_collection = [title[0] for title in title_collection]
    for title in cleaned_title_collection:
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_count' INTEGER DEFAULT 0")
        cursor.execute(f"ALTER TABLE TF_IDF_titles ADD COLUMN '{title}_TF_IDF' REAL DEFAULT 0.0")

    cursor.connection.commit()

def compute_TF_IDF_with_retry(database_path: str, term: str, chunk: str, index: int, total_words_in_chunk: int, total_documents: int, number_documents_with_term: int, MAX_RETRIES=5, RETRY_DELAY=1) -> None:
    attempts = 0
    while attempts < MAX_RETRIES:
        try:
            conn = sqlite3.connect(database_path)
            cursor = conn.cursor()
            term_count = chunk.count(term)
            cursor.execute(f"UPDATE TF_IDF_table_{index} SET '{term}_count' = ? WHERE chunk_text = ?", (term_count, chunk))
            term_frequency = term_count / total_words_in_chunk if total_words_in_chunk > 0 else 0
            document_frequency = total_documents / number_documents_with_term if number_documents_with_term > 0 else 0
            tf_idf_value = term_frequency * log10(1 + document_frequency)
            cursor.execute(f"UPDATE TF_IDF_table_{index} SET '{term}_TF_IDF' = ? WHERE chunk_text = ?", (tf_idf_value, chunk))
            conn.commit()
            cursor.close()
            conn.close()
            break
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                attempts += 1
                time.sleep(RETRY_DELAY)
            else:
                raise
        except Exception as e:
            print(f"Error while computing TF-IDF for term '{term}': {e}")
            raise
    else:
        print(f"Failed to compute TF-IDF after {MAX_RETRIES} attempts for term '{term}' in chunk {chunk[:50]}...")

def process_in_parallel_TF_IDF_with_retry(database_path: str, number_of_tables: int, MAX_RETRIES=5, RETRY_DELAY=1) -> None:
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    TOTAL_TEXT_CHUNK = cursor.execute("SELECT COUNT(*) FROM pdf_chunks").fetchone()[0]
    conn.close()

    for root_word, index in zip(batch_collect_words(sqlite3.connect(database_path).cursor()), range(number_of_tables)):
        thread_list = []

        for word in root_word:
            # Establish a new connection inside the loop for each word
            conn = sqlite3.connect(database_path)
            cursor = conn.cursor()
            total_document_with_term = cursor.execute(f"SELECT COUNT(*) FROM TF_IDF_table_{index} WHERE '{word}_count' > 0").fetchone()[0]
            text_chunks = cursor.execute(f"SELECT chunk_text FROM pdf_chunks").fetchall()
            conn.close()

            for chunk_tuple in text_chunks:
                text_chunk = chunk_tuple[0]
                total_words_in_chunk = len(text_chunk.split())
                thread = threading.Thread(
                    target=compute_TF_IDF_with_retry,
                    args=(database_path, word, text_chunk, index, total_words_in_chunk, TOTAL_TEXT_CHUNK, total_document_with_term, MAX_RETRIES, RETRY_DELAY)
                )
                thread.start()
                thread_list.append(thread)

        for thread in thread_list:
            thread.join()

def computeTFIDF(database_path: str) -> None:
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    NUMER_OF_WORDS = cursor.execute("SELECT COUNT(*) FROM coverage_analysis").fetchone()[0]
    BATCH_SIZE = 975
    number_of_tables = (NUMER_OF_WORDS + BATCH_SIZE - 1) // BATCH_SIZE

    setup_TF_IDF_tables(cursor, number_of_tables)

    process_in_parallel_TF_IDF_with_retry(database_path, number_of_tables)

    conn.close()

computeTFIDF(path.chunk_database_path)
