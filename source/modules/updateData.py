import os
import sqlite3
import concurrent.futures
import time
import fitz  # PyMuPDF
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from collections import defaultdict
import modules.path as path

# Utility Functions
def get_file_list(folder_path: str, file_type: str) -> list:
    """Return a list of files in a given folder with the specified file type."""
    if not os.path.isdir(folder_path):
        raise ValueError(f"The provided folder path does not exist: {folder_path}")
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(file_type)]

def get_current_timestamp() -> str:
    """Return the current timestamp in the format YYYY-MM-DD HH:MM:SS."""
    return time.strftime("%Y-%m-%d %H:%M:%S")

def execute_query(db_name: str, query: str, params: tuple = ()) -> None:
    """Execute a single SQL query."""
    try:
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
    except sqlite3.Error as e:
        log_message(f"Database error: {e}")

def execute_many_queries(db_name: str, query: str, params: list) -> None:
    """Execute multiple SQL queries."""
    try:
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params)
            conn.commit()
    except sqlite3.Error as e:
        log_message(f"Database error: {e}")

def log_message(message: str) -> None:
    """Log a message to the application log database."""
    db_name = path.database_path
    query = 'INSERT INTO log (timestamp, message) VALUES (datetime(\'now\'), ?);'
    try:
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (message,))
            conn.commit()
    except sqlite3.Error as e:
        print(f"Logging error: {e}")

# Database Setup Functions
def setup_database(db_name: str, reset_db: bool) -> None:
    """Set up the database with necessary tables, optionally resetting it."""
    if not db_name:
        raise ValueError("Database name cannot be empty")

    queries = [
        'DROP TABLE IF EXISTS pdf_chunks',
        'DROP TABLE IF EXISTS note_list',
        'DROP TABLE IF EXISTS pdf_index',
        'DROP TABLE IF EXISTS word_frequencies',
        'DROP TABLE IF EXISTS log',
        '''CREATE TABLE IF NOT EXISTS pdf_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS note_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_name TEXT NOT NULL,
            file_name TEXT NOT NULL,
            timestamp TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS pdf_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS word_frequencies (
            word TEXT PRIMARY KEY,
            frequency INTEGER NOT NULL)''',
        '''CREATE TABLE IF NOT EXISTS log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            message TEXT NOT NULL)'''
    ]

    if reset_db:
        for query in queries[:4]:
            execute_query(db_name, query)
    for query in queries[4:]:
        execute_query(db_name, query)

# PDF Processing Functions
def extract_text_from_pdf(pdf_file: str) -> str:
    """Extract text from a PDF file."""
    if not os.path.isfile(pdf_file):
        raise ValueError(f"PDF file does not exist: {pdf_file}")
    if not pdf_file.endswith('.pdf'):
        raise ValueError(f"File is not a PDF: {pdf_file}")

    log_message(f"Extracting text from {pdf_file}...")
    text = ""
    try:
        with fitz.open(pdf_file) as doc:
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
                log_message(f"Extracted text from page {page_num} of {pdf_file}.")
    except fitz.fitz_error as e:
        log_message(f"MuPDF error in {pdf_file}: {e}")
    except Exception as e:
        log_message(f"Error extracting text from {pdf_file}: {e}")
    return text

def split_text_into_chunks(text: str, chunk_size: int) -> list:
    """Split text into chunks of a given size."""
    if not isinstance(text, str):
        raise ValueError("Text to be split must be a string")
    if chunk_size <= 0:
        raise ValueError("Chunk size must be a positive integer")

    log_message(f"Splitting text into chunks of {chunk_size} characters...")
    try:
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
        chunks = text_splitter.split_text(text)
    except Exception as e:
        log_message(f"Error splitting text: {e}")
        chunks = []
    log_message("Finished splitting text into chunks.")
    return chunks

def store_chunks_in_db(file_name: str, chunks: list, db_name: str) -> None:
    """Store text chunks in the database."""
    if not db_name:
        raise ValueError("Database name cannot be empty")
    if not isinstance(chunks, list) or not all(isinstance(chunk, str) for chunk in chunks):
        raise ValueError("Chunks must be a list of strings")

    query = 'INSERT INTO pdf_chunks (file_name, chunk_index, chunk_text) VALUES (?, ?, ?)'
    params = [(os.path.basename(file_name), idx, chunk) for idx, chunk in enumerate(chunks)]

    max_attempts = 999
    for attempt in range(max_attempts):
        try:
            execute_many_queries(db_name, query, params)
            log_message(f"Stored {len(chunks)} chunks for {file_name} in the database.")
            return
        except sqlite3.Error:
            log_message(f"Attempt {attempt + 1} failed. Retrying...")
            time.sleep(10)

    log_message(f"Failed to insert chunks for {file_name} after {max_attempts} attempts.")

def process_file(pdf_file: str, db_name: str, chunk_size: int) -> None:
    """Process a single PDF file."""
    text = extract_text_from_pdf(pdf_file)
    if text:
        chunks = split_text_into_chunks(text, chunk_size)
        if chunks:
            store_chunks_in_db(pdf_file, chunks, db_name)

def process_files(file_list: list, db_name: str, chunk_size: int) -> None:
    """Process multiple PDF files concurrently."""
    if not isinstance(file_list, list) or not all(isinstance(file, str) for file in file_list):
        raise ValueError("File list must be a list of strings")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(lambda file: process_file(file, db_name, chunk_size), file_list)

# Note Processing Functions
def set_up_note_table(db_name: str) -> None:
    """Set up the note table in the database."""
    query = '''CREATE TABLE IF NOT EXISTS note_list (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   note_name TEXT NOT NULL,
                   file_name TEXT NOT NULL,
                   timestamp TEXT NOT NULL)'''
    execute_query(db_name, query)

def process_note_file(note_file: str, db_name: str) -> tuple:
    """Process a single note file and return its metadata."""
    if not os.path.isfile(note_file):
        raise ValueError(f"Note file does not exist: {note_file}")
    if not note_file.endswith('.md'):
        raise ValueError(f"File is not a Markdown file: {note_file}")

    query = 'SELECT * FROM note_list WHERE file_name = ?'
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (note_file,))
        if cursor.fetchone():
            log_message(f"Skipping {note_file} because it has already been processed.")
            return None

    log_message(f"Processing {note_file}...")
    with open(note_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()[:3]
    if len(lines) < 3:
        log_message(f"Invalid format in {note_file}.")
        return None

    timestamp = lines[0].strip().split()[2:]
    timestamp = ' '.join(timestamp)
    title = lines[2].strip().removeprefix("Topic: [[").removesuffix("]]")
    log_message(f"Finished processing {note_file}.")
    return (title, note_file, timestamp)

def store_note_files_in_db(note_files: list, db_name: str) -> None:
    """Store note file metadata in the database."""
    query = 'INSERT INTO note_list (note_name, file_name, timestamp) VALUES (?, ?, ?)'
    max_attempts = 999

    for attempt in range(max_attempts):
        try:
            execute_many_queries(db_name, query, note_files)
            log_message("Stored note files in the database.")
            return
        except sqlite3.Error:
            log_message(f"Attempt {attempt + 1} failed. Retrying...")
            time.sleep(10)

    log_message(f"Failed to insert note files after {max_attempts} attempts.")

def process_note_files(note_files: list, db_name: str) -> None:
    """Process multiple note files."""
    set_up_note_table(db_name)
    valid_notes = [process_note_file(note_file, db_name) for note_file in note_files]
    valid_notes = [note for note in valid_notes if note]
    if valid_notes:
        store_note_files_in_db(valid_notes, db_name)

# Word Frequency Functions
def calculate_word_frequencies(db_name: str) -> None:
    """Calculate word frequencies from the text chunks stored in the database."""
    if not db_name:
        raise ValueError("Database name cannot be empty")

    def retrieve_chunks_in_batches():
        with sqlite3.connect(db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pdf_chunks")
            total_chunks = cursor.fetchone()[0]
            batch_size = 500
            for offset in range(0, total_chunks, batch_size):
                cursor.execute(f"SELECT chunk_text FROM pdf_chunks LIMIT {batch_size} OFFSET {offset}")
                yield cursor.fetchall()

    word_frequencies = defaultdict(int)
    for batch in retrieve_chunks_in_batches():
        for (text,) in batch:
            words = re.findall(r'\b\w+\b', text.lower())
            for word in words:
                word_frequencies[word] += 1

    query = 'INSERT INTO word_frequencies (word, frequency) VALUES (?, ?) ' \
            'ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency'
    params = [(word, freq) for word, freq in word_frequencies.items()]

    max_attempts = 999
    for attempt in range(max_attempts):
        try:
            execute_many_queries(db_name, query, params)
            log_message("Stored word frequencies in the database.")
            return
        except sqlite3.Error:
            log_message(f"Attempt {attempt + 1} failed. Retrying...")
            time.sleep(10)

    log_message(f"Failed to insert word frequencies after {max_attempts} attempts.")

# Main Execution
def update_data():
    """Main function to update the data by processing PDFs, notes, and calculating word frequencies."""
    db_name = path.database_path
    pdf_folder_path = path.pdf_path
    note_folder_path = path.note_path
    reset_db = True  # Change this flag as needed
    chunk_size = 5000  # Adjust the chunk size as needed

    setup_database(db_name, reset_db)
    pdf_files = get_file_list(pdf_folder_path, '.pdf')
    note_files = get_file_list(note_folder_path, '.md')

    process_files(pdf_files, db_name, chunk_size)
    process_note_files(note_files, db_name)
    calculate_word_frequencies(db_name)
