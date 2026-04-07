import sqlite3
import numpy as np
from scipy.sparse import csr_matrix
import pandas as pd
import os

DB_PATH = "data\\pdf_text.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL;")
cursor.execute("PRAGMA synchronous=NORMAL;")
cursor.execute("PRAGMA temp_store=MEMORY;")

TOP_SIM = 500

for TOP_K in [100, 200, 350, 500, 750]:
    cursor.executescript(f"""
    DROP TABLE IF EXISTS selected_tokens;
    CREATE TEMP TABLE selected_tokens AS
    SELECT word AS token
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

    print(f"Tokens: {len(tokens)}, Entries: {len(entries)}")

    rows = []
    cols = []
    data = []

    query = """
    SELECT r.token, r.file_name, r.relational_distance
    FROM relation_distance r
    JOIN selected_tokens t ON r.token = t.token
    JOIN selected_files f ON r.file_name = f.file_name
    """

    for t, e, d in cursor.execute(query):
        rows.append(entry_index[e])
        cols.append(token_index[t])
        data.append(d)

    table = csr_matrix((data, (rows, cols)), shape=(len(entries), len(tokens)), dtype=np.float32)
    print("Sparse matrix built.")
    result = table @ table.T

    print("Matrix multiplication complete.")
    output_path = f"result_topk_{TOP_K}.csv"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("file_name,similar_file,similarity\n")
        
        for i in range(result.shape[0]):
            row = result.getrow(i).toarray().ravel()
            
            top_idx = np.argpartition(-row, TOP_SIM)[:TOP_SIM]
            top_idx = top_idx[np.argsort(-row[top_idx])]
            
            for j in top_idx:
                if row[j] > 0:
                    f.write(f"{entries[i]},{entries[j]},{row[j]}\n")
    
    print(f"Results written to {output_path}")

conn.close()

TOP_K_LIST = [100, 200, 350, 500, 750, 1000]
files = [f"result_topk_{k}.csv" for k in TOP_K_LIST]

dfs = []

for k, file in zip(TOP_K_LIST, files):
    print(f"Loading {file}...")

    df = pd.read_csv(file)

    # Rename similarity column
    df = df.rename(columns={"similarity": f"similarity_{k}"})

    dfs.append(df)

    # Remove the file after loading to save space
    os.remove(file)
    print(f"Loaded and removed {file}.")

# --------------------------------------------------
# Merge all dataframes on (file_name, similar_file)
# --------------------------------------------------
merged_df = dfs[0]

for df in dfs[1:]:
    merged_df = merged_df.merge(
        df,
        on=["file_name", "similar_file"],
        how="outer"   # keep all pairs
    )

# Fill missing similarities with 0
merged_df = merged_df.fillna(0)

print("Merge complete.")

# Save
merged_df.to_csv("merged_similarity_analysis.csv", index=False)

print("Saved to merged_similarity_analysis.csv")