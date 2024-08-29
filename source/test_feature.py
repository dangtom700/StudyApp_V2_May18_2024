import sqlite3
from math import sqrt, log
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from modules.path import chunk_database_path
from modules.extract_pdf import get_title_ids, retrieve_token_list
from modules.updateLog import print_and_log

def precompute_title_vector(database_path: str) -> None:
    conn = sqlite3.connect(database_path, check_same_thread=False)
    cursor = conn.cursor()

    # Define a queue for communication between threads
    update_queue = Queue()

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

    def process_title_analysis(title_ids: list[str], words: list[str], cursor: sqlite3.Cursor) -> None:
        for title in title_ids:
            token_list = retrieve_token_list(title_id=title, cursor=cursor)
            word_counts = {word: token_list.count(word) for word in words if word in token_list}

            update_queue.put(('title_analysis', title, word_counts))

    def normalize_vector(title_ids: list[str]) -> None:
        for title in title_ids:
            length = cursor.execute(f"SELECT SUM(T_{title} * T_{title}) FROM title_analysis").fetchone()[0]
            if length:
                length = sqrt(length)
                update_queue.put(('normalize', title, length))

    def compute_TF_IDF(title_ids: list[str]) -> None:
        TOTAL_DOC = len(title_ids)
        for title in title_ids:
            total_terms = cursor.execute(f"SELECT SUM(T_{title}) FROM title_analysis").fetchone()[0]
            if total_terms:
                term_counts = cursor.execute(f"SELECT word, T_{title} FROM title_analysis").fetchall()
                
                tf_idf_data = {}
                for word, term_count in term_counts:
                    if term_count > 0:
                        tf = term_count / total_terms
                        doc_with_term = cursor.execute(f"""
                            SELECT COUNT(*) 
                            FROM title_analysis 
                            WHERE word = ? AND T_{title} > 0
                        """, (word,)).fetchone()[0]
                        idf = log(TOTAL_DOC / (1 + doc_with_term))
                        tf_idf_data[word] = tf * idf
                
                update_queue.put(('tf_idf', title, tf_idf_data))

    def update_database():
        """Dedicated function to handle database updates."""
        while True:
            task_type, title, data = update_queue.get()
            if task_type == 'title_analysis':
                update_data = [(count, word) for word, count in data.items()]
                cursor.executemany(
                    f"UPDATE title_analysis SET T_{title} = ? WHERE word = ?",
                    update_data
                )
            elif task_type == 'normalize':
                cursor.execute(f"""
                    UPDATE title_normalized
                    SET T_{title} = T_{title} / ?
                """, (data,))
            elif task_type == 'tf_idf':
                update_data = [(tf_idf, word) for word, tf_idf in data.items()]
                cursor.executemany(
                    f"UPDATE title_tf_idf SET T_{title} = ? WHERE word = ?",
                    update_data
                )
            conn.commit()
            update_queue.task_done()

    def get_words() -> list[str]:
        cursor.execute("SELECT word FROM coverage_analysis")
        return [word[0] for word in cursor.fetchall()]

    # Main flow
    start_execution_time = datetime.now()

    title_ids = get_title_ids(cursor=cursor)
    words = get_words()
    
    print_and_log("Creating tables...")
    create_tables(title_ids=title_ids)
    print_and_log("Finished creating tables.")
    
    # Start the database update thread
    updater_thread = ThreadPoolExecutor(max_workers=1)
    updater_thread.submit(update_database)
    
    print_and_log("Processing title analysis...")
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.submit(process_title_analysis, title_ids, words, cursor)
        executor.submit(normalize_vector, title_ids)
        executor.submit(compute_TF_IDF, title_ids)
    
    # Wait for all tasks to be completed
    update_queue.join()

    print_and_log("Finished processing title analysis.")
    print_and_log("Normalizing vectors...")
    print_and_log("Computing TF-IDF...")

    conn.commit()
    conn.close()

    print_and_log(f"Finished in {datetime.now() - start_execution_time}")

precompute_title_vector(chunk_database_path)