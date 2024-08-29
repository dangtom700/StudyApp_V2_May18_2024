from modules.path import chunk_database_path
from modules.extract_pdf import get_title_ids, retrieve_token_list
from modules.updateLog import print_and_log
import sqlite3
import threading
from queue import Queue
from math import sqrt, log
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

def precompute_title_vector(database_path: str, tfidf_threads: int = 4) -> None:
    # Step 1: Establish a connection to the database
    conn = sqlite3.connect(database_path, check_same_thread=False)
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
        conn.commit()

    def process_title_analysis(title_id: str, words: list[str]) -> None:
        token_list = retrieve_token_list(title_id=title_id, cursor=cursor)
        word_counts = {word: token_list.count(word) for word in words if word in token_list}
        
        # Insert word counts into title_analysis table using the queue
        for word, count in word_counts.items():
            queue.put(('update_analysis', title_id, word, count))

    def normalize_vector(title_id: str) -> None:
        length = cursor.execute(f"SELECT SUM(T_{title_id} * T_{title_id}) FROM title_analysis").fetchone()[0]
        if length:
            length = sqrt(length)
            queue.put(('normalize', title_id, None, length))

    def compute_TF_IDF(title_id: str) -> None:
        TOTAL_DOC = len(title_ids)
        total_terms = cursor.execute(f"SELECT SUM(T_{title_id}) FROM title_analysis").fetchone()[0]
        if total_terms:
            term_counts = cursor.execute(f"SELECT word, T_{title_id} FROM title_analysis").fetchall()
            for word, term_count in term_counts:
                if term_count > 0:
                    tf = term_count / total_terms
                    doc_with_term = cursor.execute(f"""
                        SELECT COUNT(*)
                        FROM title_analysis 
                        WHERE word = ? AND T_{title_id} > 0
                    """, (word,)).fetchone()[0]
                    idf = log(TOTAL_DOC / (1 + doc_with_term))
                    tfidf_value = tf * idf
                    queue.put(('tfidf', title_id, word, tfidf_value))

    def queue_processor(queue: Queue) -> None:
        while True:
            task = queue.get()
            if task is None:
                break

            if task[0] == 'update_analysis':
                _, title_id, word, count = task
                cursor.execute(f"UPDATE title_analysis SET T_{title_id} = ? WHERE word = ?", (count, word))

            elif task[0] == 'normalize':
                _, title_id, _, length = task
                cursor.execute(f"""
                    UPDATE title_normalized
                    SET T_{title_id} = T_{title_id} / ?
                """, (length,))

            elif task[0] == 'tfidf':
                _, title_id, word, tfidf_value = task
                cursor.execute(f"""
                    UPDATE title_tf_idf
                    SET T_{title_id} = ?
                    WHERE word = ?
                """, (tfidf_value, word))

            queue.task_done()

    def get_words() -> list[str]:
        cursor.execute("SELECT word FROM coverage_analysis")
        return [word[0] for word in cursor.fetchall()]

    # Main flow
    start_execution_time = datetime.now()
    title_ids = get_title_ids(cursor=cursor)
    words = get_words()

    # Step 1: Create Tables
    print_and_log("Creating tables...")
    create_tables(title_ids=title_ids)
    print_and_log("Finished creating tables.")

    # Initialize the queue
    queue = Queue(maxsize=1000)

    # Start the queue processor thread
    queue_processor_thread = threading.Thread(target=queue_processor, args=(queue,))
    queue_processor_thread.start()

    # Step 2: Process Title Analysis
    print_and_log("Processing title analysis...")
    with ThreadPoolExecutor() as executor:
        analysis_futures = [executor.submit(process_title_analysis, title, words) for title in title_ids]
        for future in as_completed(analysis_futures):
            pass  # Handle any exceptions or log progress if needed
    print_and_log("Finished processing title analysis.")
    queue.join()  # Ensure all analysis updates are completed

    # Step 3: Normalize Title Vectors
    print_and_log("Normalizing vectors...")
    with ThreadPoolExecutor() as executor:
        normalize_futures = [executor.submit(normalize_vector, title) for title in title_ids]
        for future in as_completed(normalize_futures):
            pass  # Handle any exceptions or log progress if needed
    print_and_log("Finished normalizing vectors.")
    queue.join()  # Ensure all normalization updates are completed

    # Step 4: Compute TF-IDF
    print_and_log("Computing TF-IDF...")
    with ThreadPoolExecutor(max_workers=tfidf_threads) as executor:
        tfidf_futures = [executor.submit(compute_TF_IDF, title) for title in title_ids]
        for future in as_completed(tfidf_futures):
            pass  # Handle any exceptions or log progress if needed
    print_and_log("Finished computing TF-IDF.")
    queue.join()  # Ensure all TF-IDF updates are completed

    # Stop the queue processor thread
    queue.put(None)
    queue_processor_thread.join()

    conn.commit()
    conn.close()

    print_and_log(f"Finished in {datetime.now() - start_execution_time}")

precompute_title_vector(chunk_database_path)