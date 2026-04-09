import sqlite3
import numpy as np
from scipy.sparse import csr_matrix
import polars as pl
import os

DB_PATH = "data\\pdf_text.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL;")
cursor.execute("PRAGMA synchronous=NORMAL;")
cursor.execute("PRAGMA temp_store=MEMORY;")

TOP_SIM = 50
TOP_K_LIST = [50, 100, 200, 350, 500, 750, 1000, 2000, 3000, 5000, 7500, 10000]
TOP_K_LIST =sorted(TOP_K_LIST, reverse=True)

for TOP_K in TOP_K_LIST:
    print(f"Processing TOP_K={TOP_K}...")
    cursor.executescript(f"""
    DROP TABLE IF EXISTS selected_tokens;
    CREATE TEMP TABLE selected_tokens AS
    SELECT word AS token, tf_idf
    FROM tf_idf
    ORDER BY tf_idf DESC
    LIMIT {TOP_K};

    DROP TABLE IF EXISTS selected_files;
    CREATE TEMP TABLE selected_files AS
    SELECT file_name
    FROM file_token;
    """)

    tokens = [row[0] for row in cursor.execute("SELECT token FROM selected_tokens")]
    entries = [row[0] for row in cursor.execute("SELECT file_name FROM selected_files")]

    token_index = {t: i for i, t in enumerate(tokens)}
    entry_index = {e: i for i, e in enumerate(entries)}

    print(f"Tokens: {len(tokens)}\nToken example: ...,{tokens[-8:]}") # Last 8 tokens

    rows = []
    cols = []
    data = []
    data_mod = []

    query = """
    SELECT r.token, r.file_name, r.relational_distance, t.tf_idf
    FROM relation_distance r
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
    result_raw = table @ table.T
    result_mod = table_mod @ table_mod.T

    print("Matrix multiplication complete.")
    output_path = f"result_topk_{TOP_K}.csv"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("file_name,similar_file,similarity_raw,similarity_mod\n")
        
        for i in range(result_mod.shape[0]):
            start_mod = result_mod.indptr[i]
            end_mod = result_mod.indptr[i+1]
            
            if start_mod == end_mod:
                continue
                
            cols_mod = result_mod.indices[start_mod:end_mod]
            vals_mod = result_mod.data[start_mod:end_mod]
            
            if len(vals_mod) > TOP_SIM:
                # Get indices of top values within the sparse row
                top_idx_rel = np.argpartition(-vals_mod, TOP_SIM)[:TOP_SIM]
                # Sort the top values
                top_idx_rel = top_idx_rel[np.argsort(-vals_mod[top_idx_rel])]
            else:
                # If less than TOP_SIM elements, just sort all available
                top_idx_rel = np.argsort(-vals_mod)
                
            top_cols = cols_mod[top_idx_rel]
            top_vals_mod_final = vals_mod[top_idx_rel]
            
            # Map raw values for this specific row for fast lookup
            start_raw = result_raw.indptr[i]
            end_raw = result_raw.indptr[i+1]
            cols_raw = result_raw.indices[start_raw:end_raw]
            vals_raw = result_raw.data[start_raw:end_raw]
            raw_dict = dict(zip(cols_raw, vals_raw))
            
            for j, val_mod in zip(top_cols, top_vals_mod_final):
                val_raw = raw_dict.get(j, 0.0)
                if val_mod > 0 or val_raw > 0:
                    f.write(f"{entries[i]},{entries[j]},{val_raw},{val_mod}\n")
    
    print(f"Results written to {output_path}")

conn.close()

files = [f"result_topk_{k}.csv" for k in TOP_K_LIST]

dfs = []

for k, file in zip(TOP_K_LIST, files):
    print(f"Loading {file}...")

    df = pl.read_csv(file)

    df = df.select([
        pl.col("file_name"),
        pl.col("similar_file"),
        pl.col("similarity_raw").cast(pl.Float64).alias("distance_raw"),
        pl.col("similarity_mod").cast(pl.Float64).alias("distance_mod"),
        pl.lit(k, dtype=pl.Int32).alias("top_K")
    ])

    dfs.append(df)

    # Remove the file after loading to save space
    os.remove(file)
    print(f"Loaded and removed {file}.")

# --------------------------------------------------
# Combine all dataframes
# --------------------------------------------------
merged_df = pl.concat(dfs)

print("Merge complete.")

# Save
merged_df.write_csv("merged_similarity_analysis.csv")

print("Saved to merged_similarity_analysis.csv")