"""
The fast document-similarity path: one sparse matrix product over the top-k
TF-IDF tokens, writing `item_matrix`.

`comparison` -- word_tokenizer --mappingItemMatrix -- is the pipeline's default
similarity table and what --expandTopics expands over. This one uses a lower
cutoff and different weighting, and is the only table carrying distance_mod.
config/schema.sql describes both side by side.
"""

import sqlite3
import ujson as json  # Much faster
import math
import numpy as np
from scipy.sparse import csr_matrix
from modules import schema
from modules.path import chunk_database_path, token_json_path
from os import listdir, path

GLOBAL_JSON_PATH = "data/global_word_freq.json"
MIN_THRES_FREQ = 4
BUFFER_SIZE = 1000

def compute_item_matrix(top_k=1000, batch_size=20000, similarity_cutoff = 0.3):
    conn = sqlite3.connect(chunk_database_path, timeout=60.0)
    cursor = conn.cursor()

    if not schema.require(conn, {
        'file_token': 'word_tokenizer --computeRelationalDistance',
        'relation_distance_filtered': 'word_tokenizer --computeRelationalDistance',
        'tf_idf': 'word_tokenizer --computeTFIDF',
    }, '--computeItemMatrix'):
        conn.close()
        return

    # --- Aggressive write optimization ---
    cursor.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=OFF;
    PRAGMA temp_store=MEMORY;
    PRAGMA cache_size=-300000;
    """)

    # --- Target table ---
    # Every run recomputes the whole matrix, so this stage always resets its output.
    schema.reset(conn, ['item_matrix'])

    print(f"Processing item matrix with top_k={top_k}...")

    # --- Token + file selection ---
    cursor.executescript(f"""
    DROP TABLE IF EXISTS selected_tokens;
    CREATE TEMP TABLE selected_tokens AS
    SELECT word AS token, tf_idf
    FROM tf_idf
    ORDER BY tf_idf DESC
    LIMIT {top_k};

    DROP TABLE IF EXISTS selected_files;
    CREATE TEMP TABLE selected_files AS
    SELECT file_name
    FROM file_token;
    """)

    tokens = [row[0] for row in cursor.execute("SELECT token FROM selected_tokens")]
    entries = [row[0] for row in cursor.execute("SELECT file_name FROM selected_files")]

    token_index = {t: i for i, t in enumerate(tokens)}
    entry_index = {e: i for i, e in enumerate(entries)}

    # --- Build sparse matrix (float16) ---
    rows, cols, data, data_mod = [], [], [], []
    query = """
    SELECT r.token, r.file_name, r.relational_distance, t.tf_idf
    FROM relation_distance_filtered r
    JOIN selected_tokens t ON r.token = t.token
    JOIN selected_files f ON r.file_name = f.file_name
    """

    for t, e, d, tidf in cursor.execute(query):
        rows.append(entry_index[e])
        cols.append(token_index[t])
        data.append(d)
        data_mod.append(d + tidf)

    table = csr_matrix((data, (rows, cols)), shape=(len(entries), len(tokens)), dtype=np.float32)
    table_mod = csr_matrix((data_mod, (rows, cols)), shape=(len(entries), len(tokens)), dtype=np.float32)

    print("Sparse matrix built.")

    # --- Multiply ---
    result = table @ table.T
    result_mod = table_mod @ table_mod.T
    print("Matrix multiplication complete.")

    # --- Insert everything (upper triangle only) ---
    insert_query = """
    INSERT INTO item_matrix(source_id, target_id, distance, distance_mod)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(source_id, target_id) DO UPDATE SET
        distance=excluded.distance,
        distance_mod=excluded.distance_mod
    """

    buffer = []

    cursor.execute("BEGIN TRANSACTION;")

    for i in range(result.shape[0]):
        start = result.indptr[i]
        end = result.indptr[i + 1]

        cols_i = result.indices[start:end]
        vals_i = result.data[start:end]
        vals_mod_i = result_mod.data[start:end]

        for j, val, val_mod in zip(cols_i, vals_i, vals_mod_i):
            # --- Only upper triangle ---
            if j <= i:
                continue

            if val <=similarity_cutoff or val_mod <=similarity_cutoff:  # Skip very low similarity pairs
                continue
            
            buffer.append((entries[i], entries[j], float(val), float(val_mod)))

            if len(buffer) >= batch_size:
                cursor.executemany(insert_query, buffer)
                buffer.clear()

    # Flush remaining
    if buffer:
        cursor.executemany(insert_query, buffer)

    conn.commit()
    conn.close()

    print("Full upper triangle inserted.")
