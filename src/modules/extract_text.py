import concurrent.futures as cf
import os
import sqlite3
import re

from modules.path import chunk_database_path
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.documents import Document
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

# --- Config ---
MODEL_NAMES = [
    "llama3:latest",
    "llama3.2:latest",
    "phi3.5:latest",
    "gemma:latest",
    "deepseek-r1:8b"
]
DATA_DIR = "data"
LOG_FILE = "PROMPT.txt"
SESSION_ID = "default"
DB_PATH = chunk_database_path
INDEX_PATH = "faiss_index"
BATCH_SIZE = 100
EMBEDDING_MODEL = "nomic-embed-text"
MAX_THREADS = 8

# -----------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------

"""
From a raw dataset,
1. Refine the text (remove special characters, reduce multiple spaces)
2. Chunk the text into chunks of size chunk_size
3. Create embeddings for each chunk
4. Save text chunks and embeddings to a database
"""

def text_to_chunks(text, chunk_size):
    """Split text into chunks of approximately `chunk_size` words."""
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def clean_text_for_extracted_data(text):
    """Remove non-word characters and reduce multiple spaces."""
    return re.sub(r'\s+', ' ', re.sub(r'\W+', ' ', text)).strip()

def save_chunks_to_file(file_path, chunks, text_embedder: Embeddings):
    """Save each chunk to a new line in a file."""
    multi_embedding = text_embedder.embed_documents(chunks)
    with open(file_path, "w", encoding="utf-8") as f:
        for chunk, embedding in zip(chunks, multi_embedding):
            embedding = ", ".join(map(str, embedding))
            f.write(f"{chunk} : {embedding}\n")
        
def process_file(file, source_folder, chunk_size, dataset_folder, text_embedder):
    """Read and chunk a file, saving the output to dataset_folder."""
    if not file.endswith(".txt"):
        return

    print(f"[INFO] Processing {file}...")

    try:
        with open(os.path.join(source_folder, file), "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = clean_text_for_extracted_data(raw_text)
        chunks = text_to_chunks(cleaned_text, chunk_size)

        output_path = os.path.join(dataset_folder, file)
        save_chunks_to_file(output_path, chunks, text_embedder)

        print(f"[INFO] Completed {file} with {len(chunks)} chunks.")
    except Exception as e:
        print(f"[ERROR] Failed to process {file}: {e}")

def insert_chunks_into_db(dataset_folder, db_path):
    """Insert chunked data from dataset_folder into the SQLite database."""
    print("[INFO] Inserting chunks into database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for file in os.listdir(dataset_folder):
        file_path = os.path.join(dataset_folder, file)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for chunk_id, chunk_text in enumerate(lines):
                cursor.execute("""
                    INSERT OR IGNORE INTO pdf_chunks (file_name, chunk_id, chunk_text)
                    VALUES (?, ?, ?)
                """, (file, chunk_id, chunk_text.strip()))
        except Exception as e:
            print(f"[ERROR] Failed to insert chunks from {file}: {e}")

    conn.commit()
    conn.close()
    print("[INFO] Database insertion completed.")

# -----------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------

def extract_text(SOURCE_FOLDER, DEST_FOLDER, CHUNK_SIZE=512, DB_PATH=chunk_database_path):
    """
    Processes .txt files in SOURCE_FOLDER by chunking their text and storing the results
    in a SQLite database at DB_PATH.
    """
    os.makedirs(DEST_FOLDER, exist_ok=True)

    # Step 1: Setup Database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS pdf_chunks (
            file_name TEXT,
            chunk_id INTEGER,
            chunk_text TEXT,
            embedding TEXT,
            PRIMARY KEY (file_name, chunk_id)
        )
    """)
    conn.commit()
    conn.close()

    # Step 1.1: Create embeddings
    text_embedder = OllamaEmbeddings(model=EMBEDDING_MODEL, 
                                     num_thread=MAX_THREADS)

    # Step 2: Process new files
    ready_files = [f for f in os.listdir(SOURCE_FOLDER) if f.endswith(".txt")]
    completed_files = set(os.listdir(DEST_FOLDER))
    new_files = [f for f in ready_files if f not in completed_files]

    if not new_files:
        print("[INFO] No new files to process.")
    else:
        print(f"[INFO] Found {len(new_files)} new files to process.")

        with cf.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
            futures = [
                executor.submit(process_file, f, SOURCE_FOLDER, CHUNK_SIZE, DEST_FOLDER, text_embedder)
                for f in new_files
            ]
            for future in cf.as_completed(futures):
                future.result()  # This will raise exceptions if any occur inside threads

        # Step 3: Insert into database
        insert_chunks_into_db(DEST_FOLDER, DB_PATH)

    # Check if all files have been processed
    completed_files = set(os.listdir(DEST_FOLDER))
    if len(completed_files) == len(ready_files):
        print("[INFO] All files have been processed.")
    else:
        print(f"[INFO] {len(ready_files) - len(completed_files)} files have not been processed.")
