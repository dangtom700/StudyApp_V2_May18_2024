import sqlite3
import modules.path as path
from modules.updateLog import print_and_log
from modules.extract_pdf import get_title_ids, retrieve_token_list
from math import log, sqrt
from datetime import datetime

def precompute_title_vector(database_path: str) -> None:
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    def create_tables(title_ids: list) -> None:
        cursor.execute("DROP TABLE IF EXISTS title_analysis")
        cursor.execute("DROP TABLE IF EXISTS title_normalized")
        cursor.execute("DROP TABLE IF EXISTS title_tf_idf")

        # Create command strings
        command_fill_INT = ', '.join([f"T_{title_id} INTEGER DEFAULT 0" for title_id in title_ids])
        command_fill_REAL = ', '.join([f"T_{title_id} REAL DEFAULT 0.0" for title_id in title_ids])
        # Create title_analysis and title_normalized tables
        cursor.execute(f"""
            CREATE TABLE title_analysis (
                word TEXT PRIMARY KEY, 
                {command_fill_INT},
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE title_normalized (
                word TEXT PRIMARY KEY,
                {command_fill_REAL},
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        # Insert data into tables
        cursor.execute("INSERT INTO title_analysis (word) SELECT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_normalized (word) SELECT word FROM coverage_analysis")

        # Create title_tf_idf table
        cursor.execute("CREATE TABLE title_tf_idf AS SELECT * FROM title_normalized")

    def process_title_analysis(title_ids: list[str], words: list[str], cursor: sqlite3.Cursor) -> None:
        for title in title_ids:
            token_list = retrieve_token_list(title_id=title, cursor=cursor)

            for word in words:
                # Using parameterized query to avoid SQL injection
                query = f"UPDATE title_analysis SET T_{title} = T_{title} + ? WHERE word = ?"
                cursor.execute(query, (token_list.count(word), word))

        # Commit changes once after the loop
        conn.commit()

    def normalize_vector(title_ids: list[str]) -> None:
        for title in title_ids:
            length = cursor.execute(f"SELECT SUM(T_{title} * T_{title}) FROM title_analysis").fetchone()[0]
            if length == 0:
                continue
            length = sqrt(length)
            cursor.execute(f"""
                UPDATE title_normalized
                SET T_{title} = 
                    (SELECT T_{title} FROM title_analysis WHERE title_normalized.word = title_analysis.word) / ?
            """, (length,))
        conn.commit()

    def compute_TF_IDF(title_ids: list[str]) -> None:
        TOTAL_DOC = len(title_ids)
        for title in title_ids:
            total_terms = cursor.execute(f"SELECT SUM(T_{title}) FROM title_analysis").fetchone()[0]
            if total_terms == 0:
                continue  # Skip if no terms are found
            
            term_counts = cursor.execute(f"SELECT word, T_{title} FROM title_analysis").fetchall()
            
            for word, term_count in term_counts:
                if term_count == 0:
                    continue
                
                tf = term_count / total_terms
                doc_term = cursor.execute(f"""
                    SELECT * 
                    FROM title_analysis 
                    WHERE word = ?
                """, (word,)).fetchall()[0]
                doc_with_term = len([count for count in doc_term[1:] if count > 0])
                
                idf = log(TOTAL_DOC / (1 + doc_with_term))
                cursor.execute(f"""
                    UPDATE title_tf_idf 
                    SET T_{title} = ?""", (tf * idf,))
                print(f"Word: {word}, TF-IDF: {tf * idf}")
    
    def get_words() -> list[str]:
        cursor.execute("SELECT word FROM coverage_analysis")
        return [word[0] for word in cursor.fetchall()]

    # Main flow
    start_execution_time = datetime.now()

    title_ids = get_title_ids(cursor=cursor)
    word_essentials = get_words()
    
    print_and_log("Creating tables...")
    create_tables(title_ids=title_ids)
    print_and_log("Finished creating tables.")
    # order pdf_chunks by id
    cursor.execute("SELECT id FROM pdf_chunks ORDER BY id ASC")
    # counting
    print_and_log("Processing title analysis...")
    process_title_analysis(title_ids=title_ids, words=word_essentials, cursor=cursor)
    print_and_log("Finished processing title analysis.")
    # normalizing
    print_and_log("Normalizing vectors...")
    normalize_vector(title_ids=title_ids)
    print_and_log("Finished normalizing vectors.")
    # computing TF-IDF
    print_and_log("Computing TF-IDF...")
    compute_TF_IDF(title_ids=title_ids)
    print_and_log("Finished computing TF-IDF.")

    conn.commit()
    conn.close()

    print_and_log(f"Finished in {datetime.now() - start_execution_time}")

precompute_title_vector(path.chunk_database_path)