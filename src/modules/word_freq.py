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

# Retrieve and clean text chunks for a single title
def retrieve_token_list(title_id: str, cursor: sqlite3.Cursor) -> dict[str, int]:
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

    return clean_text(merged_chunk_text)

# Process chunks in batches and store word frequencies in individual JSON files
def process_chunks_in_batches(cursor: sqlite3.Cursor) -> None:
    title_ids = get_title_ids(cursor)

    # Process title IDs in parallel
    with ThreadPoolExecutor() as executor:
        for title_id, word_freq in zip(title_ids, executor.map(retrieve_token_list, title_ids, [cursor] * len(title_ids))):
            # Dump word frequencies for each title into a separate JSON file
            with open(f'data\\{title_id}.json', 'w', encoding='utf-8') as f:
                dump(word_freq, f, ensure_ascii=False, indent=4)

    print_and_log("All titles processed and word frequencies stored in individual JSON files.")

def process_word_frequencies_in_batches():
    conn = sqlite3.connect(chunk_database_path, check_same_thread=False)
    cursor = conn.cursor()

    def create_table():
        cursor.execute("DROP TABLE IF EXISTS word_frequencies")
        cursor.execute("""CREATE TABLE word_frequencies (
            word TEXT PRIMARY KEY,
            frequency INTEGER)
        """)

    create_table()

    print_and_log("Starting batch processing of chunks...")
    process_chunks_in_batches(cursor)
    conn.commit()
    conn.close()
    print_and_log("Processing word frequencies complete.")
