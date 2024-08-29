import sqlite3
import modules.path as path
from modules.updateLog import print_and_log, log_message
from modules.extract_pdf import clean_text
from math import log, sqrt

def precompute_title_vector(database_name: str) -> None:
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    
    def create_tables(title_ids: list) -> None:
        cursor.execute("DROP TABLE IF EXISTS title_analysis")
        cursor.execute("DROP TABLE IF EXISTS title_normalized")
        cursor.execute("DROP TABLE IF EXISTS title_tf_idf")

        # Create title_analysis and title_normalized tables
        cursor.execute("""
            CREATE TABLE title_analysis (
                word TEXT PRIMARY KEY, 
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        cursor.execute("""
            CREATE TABLE title_normalized (
                word TEXT PRIMARY KEY, 
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        
        for title_id in title_ids:
            cursor.execute(f"ALTER TABLE title_analysis ADD COLUMN 'title_{title_id}' INTEGER DEFAULT 0")
            cursor.execute(f"ALTER TABLE title_normalized ADD COLUMN 'title_{title_id}' REAL DEFAULT 0.0")

        # Create title_tf_idf table with the same structure as title_normalized
        cursor.execute("CREATE TABLE title_tf_idf AS SELECT * FROM title_normalized WHERE 1 = 0")

        # Insert words into title_analysis and title_normalized
        cursor.execute("INSERT INTO title_analysis (word) SELECT DISTINCT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_normalized (word) SELECT DISTINCT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_tf_idf (word) SELECT DISTINCT word FROM coverage_analysis")

        conn.commit()

    def retrieve_chunk_and_title_in_batch(batch_size: int):
        offset = 0
        while True:
            cursor.execute("SELECT file_name, chunk_text FROM pdf_chunks LIMIT ? OFFSET ?", (batch_size, offset))
            raw_data = cursor.fetchall()
            if not raw_data:
                break
            yield raw_data
            offset += batch_size

    def normalize_vector(title_ids: list[str]) -> None:
        for title in title_ids:
            length = cursor.execute(f"SELECT SUM(title_{title} * title_{title}) FROM title_analysis").fetchone()[0]
            length = sqrt(length)
            cursor.execute(f"""
                UPDATE title_normalized
                SET title_{title} = 
                    (SELECT title_{title} FROM title_analysis WHERE title_normalized.word = title_analysis.word) / ?
            """, (1 + length,))
        conn.commit()

    def compute_TF_IDF(title_ids: list[str]) -> None:
        DOCUMENT_COUNT = len(title_ids)
        for title in title_ids:
            total_terms = cursor.execute(f"SELECT SUM(title_{title}) FROM title_analysis").fetchone()[0]
            if total_terms == 0:
                continue  # Skip if no terms are found
            
            term_counts = cursor.execute(f"SELECT word, title_{title} FROM title_analysis").fetchall()
            
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
                
                idf = log(DOCUMENT_COUNT / (1 + doc_with_term))
                cursor.execute(f"""
                    UPDATE title_tf_idf 
                    SET title_{title} = ? 
                    WHERE word = ?
                """, (tf * idf, word))
            conn.commit()

    # Main flow
    cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0")
    titles = cursor.fetchall()
    title_ids = [title[0] for title in titles]
    print_and_log(f"Found {len(title_ids)} titles.")

    cursor.execute("SELECT word FROM coverage_analysis")
    words = {word[0]: 0 for word in cursor.fetchall()}
    print_and_log(f"Found {len(words)} words.")

    print_and_log("Creating tables...")
    create_tables(title_ids=title_ids)

    print_and_log("Retrieving and processing chunks...")
    buffer = None
    BATCH_SIZE = 100
    
    for raw_data in retrieve_chunk_and_title_in_batch(batch_size=BATCH_SIZE):
        for file_name, chunk_text in raw_data:
            if not file_name.endswith(".pdf"):
                continue

            if buffer is None or file_name != buffer:
                if buffer:
                    log_message(f"Processing {buffer}")
                    ID_title = cursor.execute("SELECT id FROM file_list WHERE file_name = ?", (buffer.removesuffix('.pdf'),)).fetchone()[0]
                    cursor.executemany(
                        f"UPDATE title_analysis SET 'title_{ID_title}' = ? WHERE word = ?",
                        [(words[word], word) for word in words]
                    )
                    conn.commit()
                    log_message(f"Processed {buffer}")

                words = {word: 0 for word in words}  # Reset word counts
                buffer = file_name

            filtered_list = clean_text(chunk_text)
            for word in filtered_list:
                if word in words:
                    words[word] += 1

    # Final processing for the last buffer
    if buffer:
        log_message("Processing last buffer")
        ID_title = cursor.execute("SELECT id FROM file_list WHERE file_name = ?", (buffer.removesuffix('.pdf'),)).fetchone()[0]
        cursor.executemany(
            f"UPDATE title_analysis SET 'title_{ID_title}' = ? WHERE word = ?",
            [(words[word], word) for word in words]
        )
        conn.commit()
        log_message(f"Processed {buffer}")
    
    # Normalizing vectors
    print_and_log("Normalizing vectors...")
    normalize_vector(title_ids=title_ids)
    print_and_log("Finished normalizing vectors.")

    # Compute TF-IDF
    print_and_log("Computing TF-IDF...")
    compute_TF_IDF(title_ids=title_ids)
    print_and_log("Finished computing TF-IDF.")

    conn.commit()
    conn.close()

precompute_title_vector(path.chunk_database_path)