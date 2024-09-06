import os
import sqlite3
import re
from collections import defaultdict
from modules.path import chunk_database_path
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from modules.updateLog import print_and_log
from concurrent.futures import ThreadPoolExecutor
from json import dump

# One-time compiled regex pattern
REPEATED_CHAR_PATTERN = re.compile(r"([a-zA-Z])\1{2,}")
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))

def has_repeats_regex(word, n=3):
    return bool(REPEATED_CHAR_PATTERN.search(word))

def clean_text(text) -> dict[str, int]:
    # Remove punctuation and convert to lowercase
    text = re.sub(r'[^\w\s]', '', text).lower()

    # Split text into tokens
    tokens = text.split()

    # Define a function to filter tokens
    def pass_conditions(word):
        return (len(word) < 12 and
                word.isalpha() and 
                not has_repeats_regex(word))

    # Filter tokens based on conditions and apply stemming
    filtered_tokens = defaultdict(int)
    for token in tokens:
        root_word = stemmer.stem(token)
        if pass_conditions(root_word):
            filtered_tokens[root_word] += 1

    return filtered_tokens

# Retrieve title IDs from the database
def get_title_ids(cursor: sqlite3.Cursor) -> list[str]:
    cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0")
    return [title[0] for title in cursor.fetchall()]

# Retrieve and clean text chunks for a single title (each thread gets its own connection and cursor)
def retrieve_token_list(title_id: str, database: str) -> dict[str, int]:
    # Create a new connection and cursor for this thread
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT chunk_count, start_id FROM file_list WHERE id = ?", (title_id,))
        result = cursor.fetchone()

        if result is None:
            raise ValueError(f"No data found for title ID: {title_id}")

        chunk_count, start_id = result

        cursor.execute("""
            SELECT chunk_text FROM pdf_chunks
            LIMIT ? OFFSET ?""", (chunk_count, start_id))
        
        cleaned_chunks = [chunk[0] for chunk in cursor.fetchall()]
        merged_chunk_text = "".join(cleaned_chunks)
    finally:
        conn.close()  # Close the connection to avoid memory leaks

    return clean_text(merged_chunk_text)

# Process chunks in batches and store word frequencies in individual JSON files
def process_chunks_in_batches(database: str) -> None:
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    title_ids = get_title_ids(cursor)
    global_word_freq = defaultdict(int)

    # Ensure the 'data' directory exists
    os.makedirs('data', exist_ok=True)
    cwd = os.path.join(os.getcwd(), 'data')  # Get the path of the 'data' directory

    # Process title IDs in parallel (each thread gets its own connection)
    with ThreadPoolExecutor(max_workers=4) as executor:
        for title_id, word_freq in zip(title_ids, executor.map(retrieve_token_list, title_ids, [database] * len(title_ids))):
            global_word_freq.update(word_freq)

            # Dump word frequencies for each title into a separate JSON file
            json_file_path = os.path.join(cwd, f'{title_id}.json')
            with open(json_file_path, 'w', encoding='utf-8') as f:
                dump(word_freq, f, ensure_ascii=False, indent=4)

    print_and_log("All titles processed and word frequencies stored in individual JSON files.")

    # Insert global word frequencies into the database
    cursor.executemany('''
        INSERT INTO word_frequencies (word, frequency)
        VALUES (?, ?)
        ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency
    ''', global_word_freq.items())

    conn.commit()
    conn.close()
    print_and_log("Global word frequencies inserted into the database.")

def process_word_frequencies_in_batches():
    conn = sqlite3.connect(chunk_database_path, check_same_thread=False)
    cursor = conn.cursor()

    def create_table():
        cursor.execute("DROP TABLE IF EXISTS word_frequencies")
        cursor.execute("""CREATE TABLE word_frequencies (
            word TEXT PRIMARY KEY,
            frequency INTEGER DEFAULT 0)
        """)

    create_table()

    print_and_log("Starting batch processing of chunks...")
    process_chunks_in_batches(database=chunk_database_path)
    conn.commit()
    conn.close()
    print_and_log("Processing word frequencies complete.")
