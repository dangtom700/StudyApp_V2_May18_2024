import sqlite3
import ujson as json  # Much faster
import math
from modules.path import chunk_database_path, token_json_path
from os import listdir, path

GLOBAL_JSON_PATH = "data/global_word_freq.json"
MIN_THRES_FREQ = 4
BUFFER_SIZE = 1000

def computeTFIDF():
    conn = sqlite3.connect(chunk_database_path)
    cursor = conn.cursor()

    # Speed-boosting pragmas
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous = OFF;")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tf_idf (
            word TEXT PRIMARY KEY,
            freq INTEGER,
            doc_count INTEGER,
            tf_idf REAL
        )
    """)

    # Open every JSON file in the data/token_json folder and build a global word frequency dictionary
    global_word_freq = {}
    for file in listdir(token_json_path):
        with open(path.join(token_json_path, file), "r", encoding="utf-8") as f:
            data = json.load(f)
            for word, freq in data.items():
                global_word_freq[word] = global_word_freq.get(word, 0) + freq # Add up frequencies across all files

    # Save the global word frequency dictionary to a JSON file for reference
    with open(GLOBAL_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(global_word_freq, f, ensure_ascii=False, indent=2)
    
    filtered_words = {
        word: freq for word, freq in global_word_freq.items()
        if freq >= MIN_THRES_FREQ or len(word.strip()) > 1
    }

    sum_freq = sum(filtered_words.values())

    cursor.execute("""
        SELECT token, COUNT(DISTINCT file_name)
        FROM relation_distance
        GROUP BY token
    """)
    word_doc_counts = dict(cursor.fetchall())

    total_docs = cursor.execute("SELECT COUNT(DISTINCT file_name) FROM relation_distance").fetchone()[0]

    buffer = []
    conn.execute("BEGIN TRANSACTION;")  # Wrap all insertions

    for i, (word, freq) in enumerate(filtered_words.items(), 1):
        doc_count = word_doc_counts.get(word, 0)
        tf = freq / sum_freq
        idf = math.log10((total_docs + 1) / (doc_count + 1)) + 1
        tf_idf = tf * idf

        buffer.append((word, freq, doc_count, tf_idf))

        if len(buffer) == BUFFER_SIZE:
            cursor.executemany("""
                INSERT INTO tf_idf (word, freq, doc_count, tf_idf)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    freq=excluded.freq,
                    doc_count=excluded.doc_count,
                    tf_idf=excluded.tf_idf
            """, buffer)
            buffer.clear()

    if buffer:
        cursor.executemany("""
            INSERT INTO tf_idf (word, freq, doc_count, tf_idf)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(word) DO UPDATE SET
                freq=excluded.freq,
                doc_count=excluded.doc_count,
                tf_idf=excluded.tf_idf
        """, buffer)

    conn.commit()
    conn.close()
    print("TF-IDF computation completed.")
