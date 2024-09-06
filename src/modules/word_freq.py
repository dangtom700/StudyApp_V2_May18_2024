import sqlite3
import re
from modules.path import chunk_database_path
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from modules.updateLog import print_and_log
from concurrent.futures import ThreadPoolExecutor
from json import dump

# One time complied
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
    filtered_tokens = dict()
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

# Process chunks in batches and store word frequencies
def process_chunks_in_batches(cursor: sqlite3.Cursor) -> None:

    word_frequencies = dict()
    title_ids = get_title_ids(cursor)

    # Process title IDs in parallel
    with ThreadPoolExecutor() as executor:
        for title_id in title_ids:
            sample = executor.submit(retrieve_token_list, title_id, cursor)
            word_frequencies.update(sample.result())
            dump(word_frequencies, open('data\\word_freq.json', 'a', encoding='utf-8'), ensure_ascii=False, indent=4)

    # Efficiently insert word frequencies into the database
    cursor.executemany('''
        INSERT INTO word_frequencies (word, frequency) 
        VALUES (?, ?)
        ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency
    ''', word_frequencies.items())


        # for title_id in title_ids:
        #     try:
        #         token_list = retrieve_token_list(title_id, cursor)
        #         for token in token_list:
        #             word_frequencies[token] += 1
        #     except ValueError as e:
        #         print(f"Warning: {e}")

        # # Efficiently insert word frequencies into the database
        # cursor.executemany('''
        #     INSERT INTO word_frequencies (word, frequency) 
        #     VALUES (?, ?)
        #     ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency
        # ''', word_frequencies.items())

        # conn.commit()

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
    cursor.execute("DELETE FROM word_frequencies WHERE frequency > 10")
    print("Processing word frequencies complete.")