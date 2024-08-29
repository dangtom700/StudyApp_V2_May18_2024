from modules.path import chunk_database_path
from modules.extract_pdf import get_title_ids, retrieve_token_list
from modules.updateLog import print_and_log
import sqlite3
import threading
from queue import Queue
from math import sqrt, log
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

def precompute_title_vector(database_path: str) -> None:
    conn = sqlite3.connect(database_path, check_same_thread=False)  # Allow threads
    cursor = conn.cursor()

    def create_tables(title_ids: list) -> None:
        cursor.execute("DROP TABLE IF EXISTS title_analysis")
        cursor.execute("DROP TABLE IF EXISTS title_normalized")
        cursor.execute("DROP TABLE IF EXISTS title_tf_idf")

        columns_INT = ', '.join([f"T_{title_id} INTEGER DEFAULT 0" for title_id in title_ids])
        columns_REAL = ', '.join([f"T_{title_id} REAL DEFAULT 0.0" for title_id in title_ids])

        cursor.execute(f"""
            CREATE TABLE title_analysis (
                word TEXT PRIMARY KEY, 
                {columns_INT},
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE title_normalized (
                word TEXT PRIMARY KEY,
                {columns_REAL},
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE title_tf_idf (
                word TEXT PRIMARY KEY,
                {columns_REAL},
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        cursor.execute("INSERT INTO title_analysis (word) SELECT DISTINCT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_normalized (word) SELECT DISTINCT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_tf_idf (word) SELECT DISTINCT word FROM coverage_analysis")

    def process_title_analysis(title_ids: list[str], words: list[str], queue: Queue) -> None:
        for title in title_ids:
            token_list = retrieve_token_list(title_id=title, cursor=cursor)
            word_counts = {word: token_list.count(word) for word in words if word in token_list}
            queue.put((title, word_counts))  # Enqueue the counting results

    def normalize_vector(title_ids: list[str], queue: Queue) -> None:
        for title in title_ids:
            length = cursor.execute(f"SELECT SUM(T_{title} * T_{title}) FROM title_analysis").fetchone()[0]
            if length:
                length = sqrt(length)
                for word, in cursor.execute("SELECT word FROM title_analysis").fetchall():
                    queue.put(('normalize', title, word, length))  # Enqueue the normalization data

    def compute_TF_IDF(title_ids: list[str], queue: Queue) -> None:
        TOTAL_DOC = len(title_ids)
        for title in title_ids:
            total_terms = cursor.execute(f"SELECT SUM(T_{title}) FROM title_analysis").fetchone()[0]
            if total_terms:
                term_counts = cursor.execute(f"SELECT word, T_{title} FROM title_analysis").fetchall()
                for word, term_count in term_counts:
                    if term_count > 0:
                        tf = term_count / total_terms
                        doc_with_term = cursor.execute(f"""
                            SELECT COUNT(*)
                            FROM title_analysis 
                            WHERE word = ? AND T_{title} > 0
                        """, (word,)).fetchone()[0]
                        idf = log(TOTAL_DOC / (1 + doc_with_term))
                        queue.put(('tfidf', title, word, tf * idf))  # Enqueue the TF-IDF data

    def queue_processor(queue: Queue) -> None:
        while True:
            task = queue.get()
            if task is None:  # Poison pill to shut down the thread
                break

            if task[0] == 'normalize':
                _, title, word, length = task
                cursor.execute(f"""
                    UPDATE title_normalized
                    SET T_{title} = T_{title} / ?
                    WHERE word = ?
                """, (length, word))

            elif task[0] == 'tfidf':
                _, title, word, tfidf_value = task
                cursor.execute(f"""
                    UPDATE title_tf_idf
                    SET T_{title} = ?
                    WHERE word = ?
                """, (tfidf_value, word))

            queue.task_done()

    def get_words() -> list[str]:
        cursor.execute("SELECT word FROM coverage_analysis")
        return [word[0] for word in cursor.fetchall()]

    def get_title_ids(cursor: sqlite3.Cursor) -> list[str]:
        cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0")
        return [title[0] for title in cursor.fetchall()]

    # Main flow
    start_execution_time = datetime.now()
    title_ids = get_title_ids(cursor=cursor)
    words = get_words()

    print_and_log("Creating tables...")
    create_tables(title_ids=title_ids)
    print_and_log("Finished creating tables.")

    # Initialize the queue
    queue = Queue(maxsize=1000)

    # Start the queue processor thread
    queue_processor_thread = threading.Thread(target=queue_processor, args=(queue,))
    queue_processor_thread.start()

    with ThreadPoolExecutor() as executor:
        print_and_log("Processing title analysis...")
        executor.submit(process_title_analysis, title_ids, words, queue)

        print_and_log("Normalizing vectors and computing TF-IDF...")
        executor.submit(normalize_vector, title_ids, queue)
        executor.submit(compute_TF_IDF, title_ids, queue)

    queue.join()  # Wait until all tasks in the queue are processed

    # Stop the queue processor thread
    queue.put(None)
    queue_processor_thread.join()

    conn.commit()
    conn.close()

    print_and_log(f"Finished in {datetime.now() - start_execution_time}")

precompute_title_vector(chunk_database_path)