import sqlite3
from modules.path import chunk_database_path
from modules.extract_pdf import clean_text

def precompute_title_vector(database_name: str) -> None:
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    
    def create_table(title_ids: list) -> None:
        cursor.execute("DROP TABLE IF EXISTS Title_Analysis")
        cursor.execute("CREATE TABLE Title_Analysis (word TEXT PRIMARY KEY, FOREIGN KEY(word) REFERENCES coverage_analysis(word))")
        cursor.execute("INSERT INTO Title_Analysis (word) SELECT DISTINCT word FROM coverage_analysis")
        
        for title_id in title_ids:
            cursor.execute(f"ALTER TABLE Title_Analysis ADD COLUMN 'title_{title_id}' INTEGER DEFAULT 0")

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

    # Main flow
    print("Precomputing title vector...")
    cursor.execute("SELECT id, file_path FROM file_list WHERE file_type = 'pdf' AND chunk_count IS NOT NULL")
    titles = cursor.fetchall()
    title_ids = [title[0] for title in titles]
    print(f"Found {len(title_ids)} titles.")

    print("Retrieving words...")
    cursor.execute("SELECT word FROM coverage_analysis")
    words = cursor.fetchall()
    words = {word[0]: 0 for word in words}
    print(f"Found {len(words)} words.")

    print("Creating table Title_Analysis...")
    create_table(title_ids=title_ids)
    BATCH_SIZE = 100
    print("Retrieving chunks...")

    cursor.execute("SELECT file_name FROM pdf_chunks GROUP BY file_name ORDER BY file_name ASC")
    buffer = cursor.execute("SELECT file_name FROM file_list WHERE file_type = 'pdf' AND chunk_count IS NOT NULL ORDER BY file_name ASC").fetchone()[0]
    print("Counting words based on titles...")
    
    title_word_counts = {}

    for raw_data in retrieve_chunk_and_title_in_batch(batch_size=BATCH_SIZE):
        for file_name, chunk_text in raw_data:
            if not file_name.endswith(".pdf"):
                continue

            if file_name != buffer:
                print(f"Processing {buffer}.")
                ID_title = cursor.execute("SELECT id FROM file_list WHERE file_name = ?", (buffer.removesuffix('.pdf'),)).fetchone()[0]
                word_values = [words[word] for word in words]
                
                cursor.executemany(
                    f"UPDATE Title_Analysis SET 'title_{ID_title}' = ? WHERE word = ?",
                    [(words[word], word) for word in words]
                )

                words = {word: 0 for word in words}
                conn.commit()
                buffer = file_name
                print(f"Processed {file_name}.")

            filtered_list = clean_text(chunk_text)
            for word in filtered_list:
                if word in words:
                    words[word] += 1

    # Final processing for the last buffer
    if buffer:
        ID_title = cursor.execute("SELECT id FROM file_list WHERE file_name = ?", (buffer.removesuffix('.pdf'),)).fetchone()[0]
        cursor.executemany(
            f"UPDATE Title_Analysis SET 'title_{ID_title}' = ? WHERE word = ?",
            [(words[word], word) for word in words]
        )
        conn.commit()

    print("Done.")
    conn.close()

precompute_title_vector(chunk_database_path)
