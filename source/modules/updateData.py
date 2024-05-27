import os
import sqlite3
import concurrent.futures
import time
import fitz  # PyMuPDF
import re
from langchain import RecursiveCharacterTextSplitter
from collections import defaultdict
import modules.path as path

def get_file_list(folder_path: str, file_type: str) -> list[str]:
    """Get list of files in a folder with a specific file type."""
    if not os.path.isdir(folder_path):
        raise ValueError(f"The provided folder path does not exist: {folder_path}")
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(file_type)]

def get_current_timestamp() -> str:
    """Get the current timestamp in the format "YYYY-MM-DD HH:MM:SS"."""
    return time.strftime("%Y-%m-%d %H:%M:%S")

def setup_database(db_name: str, reset_db: bool) -> None:
    """Set up the database for storing PDF chunks and word frequencies."""
    if not db_name:
        raise ValueError("Database name cannot be empty")
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    if reset_db:
        cursor.execute('DROP TABLE IF EXISTS pdf_chunks')
        cursor.execute('DROP TABLE IF EXISTS log')
        cursor.execute('DROP TABLE IF EXISTS note_list')
        cursor.execute('DROP TABLE IF EXISTS pdf_index')
        cursor.execute('DROP TABLE IF EXISTS word_frequencies')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdf_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            message TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS note_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_name TEXT NOT NULL,
            file_name TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdf_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS word_frequencies (
            word TEXT PRIMARY KEY,
            frequency INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def log_message(db_name: str, message: str) -> None:
    """Log messages into the database."""
    if not db_name:
        raise ValueError("Database name cannot be empty")
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO log (timestamp, message) VALUES (datetime('now'), ?)
    ''', (message,))
    conn.commit()
    conn.close()

def extract_text_from_pdf(pdf_file: str, db_name: str) -> str:
    """Extract text from a PDF file."""
    if not os.path.isfile(pdf_file):
        raise ValueError(f"PDF file does not exist: {pdf_file}")
    if not pdf_file.endswith('.pdf'):
        raise ValueError(f"File is not a PDF: {pdf_file}")
    
    log_message(db_name, f"Extracting text from {pdf_file}...")
    text = ""
    try:
        doc = fitz.open(pdf_file)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            log_message(db_name, f"Extracted text from page {page_num} of {pdf_file}.")
            text += page_text
    except fitz.fitz_error as e:
        log_message(db_name, f"MuPDF error in {pdf_file}: {e}")
    except Exception as e:
        log_message(db_name, f"Error extracting text from {pdf_file}: {e}")
    finally:
        if 'doc' in locals():
            doc.close()
    log_message(db_name, f"Finished extracting text from {pdf_file}.")
    return text

def split_text_into_chunks(text: str, chunk_size: int, db_name: str) -> list[str]:
    """Split text into chunks."""
    if not isinstance(text, str):
        raise ValueError("Text to be split must be a string")
    if chunk_size <= 0:
        raise ValueError("Chunk size must be a positive integer")
    
    log_message(db_name, f"Splitting text into chunks of {chunk_size} characters...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
    try:
        chunks = text_splitter.split_text(text)
    except Exception as e:
        log_message(db_name, f"Error splitting text: {e}")
        chunks = []
    log_message(db_name, f"Finished splitting text into chunks.")
    return chunks

def store_chunks_in_db(file_name: str, chunks: list[str], db_name: str) -> None:
    """Store text chunks in the database with a retry mechanism."""
    if not db_name:
        raise ValueError("Database name cannot be empty")
    if not isinstance(chunks, list) or not all(isinstance(chunk, str) for chunk in chunks):
        raise ValueError("Chunks must be a list of strings")
    
    attempt = 0
    success = False
    max_attempts = 999

    while attempt < max_attempts and not success:
        try:
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            for index, chunk in enumerate(chunks):
                cursor.execute('''
                    INSERT INTO pdf_chunks (file_name, chunk_index, chunk_text) VALUES (?, ?, ?)
                ''', (os.path.basename(file_name), index, chunk))
            conn.commit()
            success = True
        except sqlite3.Error as e:
            log_message(db_name, f"Attempt {attempt + 1} failed with error: {e}. Retrying...")
            attempt += 1
            time.sleep(5)  # Sleep for a short time before retrying
        finally:
            conn.close()
    if not success:
        log_message(db_name, f"Failed to insert chunks for {file_name} after {attempt} attempts.")
    else:
        log_message(db_name, f"Stored {len(chunks)} chunks for {file_name} in the database.")

def process_file(pdf_file: str, db_name: str, chunk_size: int) -> None:
    """Process a single PDF file: extract text, split into chunks, and store in database."""
    text = extract_text_from_pdf(pdf_file, db_name)
    if text:
        chunks = split_text_into_chunks(text, chunk_size, db_name)
        if chunks:
            store_chunks_in_db(pdf_file, chunks, db_name)

def process_files(file_list: list[str], db_name: str, chunk_size: int) -> None:
    """Process a list of files in parallel."""
    if not isinstance(file_list, list) or not all(isinstance(file, str) for file in file_list):
        raise ValueError("File list must be a list of strings")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(lambda file: process_file(file, db_name, chunk_size), file_list)

def extract_pdf_index_from_table(db_name: str) -> None:
    """Extract distinct file names from pdf_chunks and store them in pdf_index table."""
    if not db_name:
        raise ValueError("Database name cannot be empty")
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pdf_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL
        )
    ''')
    
    cursor.execute('SELECT DISTINCT file_name FROM pdf_chunks')
    file_names = cursor.fetchall()
    
    cursor.executemany('INSERT INTO pdf_index (file_name) VALUES (?)', file_names)
    
    conn.commit()
    conn.close()

def process_note_files(note_files: list[str], db_name: str) -> None:
    """Process note files and store data in note_list table."""
    if not isinstance(note_files, list) or not all(isinstance(file, str) for file in note_files):
        raise ValueError("Note files must be a list of strings")
    
    def set_up_note_table(db_name: str) -> None:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS note_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_name TEXT NOT NULL,
                file_name TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    def store_data_in_note_table(db_name: str, note_files: list[tuple[str, str, str]]) -> None:
        attempt = 0
        success = False
        max_attempts = 999
        
        while attempt < max_attempts and not success:
            try:
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM note_list')
                if cursor.fetchone():
                    log_message(db_name, "Skipping store_data_in_note_table because the table is not empty.")
                    return
                conn.executemany('''
                    INSERT INTO note_list (note_name, file_name, timestamp) VALUES (?, ?, ?)
                ''', note_files)
                conn.commit()
                success = True
            except sqlite3.Error as e:
                log_message(db_name, f"Attempt {attempt + 1} failed with error: {e}. Retrying...")
                attempt += 1
                time.sleep(5)  # Sleep for a short time before retrying
            finally:
                conn.close()
        if not success:
            log_message(db_name, f"Failed to store data in note_list after {attempt} attempts.")
        else:
            log_message(db_name, "Stored data in note_list.")

    def process_note_file(note_file: str, db_name: str) -> tuple[str, str, str]:
        if not os.path.isfile(note_file):
            raise ValueError(f"Note file does not exist: {note_file}")
        if not note_file.endswith('.md'):
            raise ValueError(f"File is not a Markdown file: {note_file}")
        
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM note_list WHERE file_name = ?', (note_file,))
        if cursor.fetchone():
            log_message(db_name, f"Skipping {note_file} because it has already been processed.")
            return None
        log_message(db_name, f"Processing {note_file}...")
        with open(note_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:3]
        if len(lines) < 3:
            log_message(db_name, f"Invalid format in {note_file}.")
            return None
        timestamp = lines[0].strip()
        title = lines[2].strip()
        log_message(db_name, f"Finished processing {note_file}.")
        conn.close()
        return (title, note_file, timestamp)

    set_up_note_table(db_name)
    valid_notes = []
    for note_file in note_files:
        result = process_note_file(note_file, db_name)
        if result:
            valid_notes.append(result)
    
    store_data_in_note_table(db_name, valid_notes)

def process_chunks_in_batches(db_name: str, batch_size=1000) -> None:
    """Process PDF chunks in batches and calculate word frequencies."""
    def retrieve_chunks_in_batches():
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pdf_chunks")
        total_chunks = cursor.fetchone()[0]
        for offset in range(0, total_chunks, batch_size):
            cursor.execute("SELECT chunk_text FROM pdf_chunks ORDER BY id LIMIT ? OFFSET ?", (batch_size, offset))
            yield [row[0] for row in cursor.fetchall()]
        conn.close()

    def merge_split_words(chunks):
        merged_chunks = []
        buffer = ''
        for chunk in chunks:
            if buffer:
                chunk = buffer + chunk
                buffer = ''
            if not chunk[-1].isspace() and not chunk[-1].isalpha():
                buffer = chunk.split()[-1]
                chunk = chunk.rsplit(' ', 1)[0]
            merged_chunks.append(chunk)
        if buffer:
            merged_chunks.append(buffer)
        return merged_chunks

    def clean_text(text):
        text = re.sub(r'[^a-zA-Z\s]', '', text).lower()
        words = text.split()
        return words

    word_frequencies = defaultdict(int)

    for chunk_batch in retrieve_chunks_in_batches():
        merged_chunks = merge_split_words(chunk_batch)
        for chunk in merged_chunks:
            cleaned_words = clean_text(chunk)
            for word in cleaned_words:
                word_frequencies[word] += 1

    log_message(db_name, "Storing word frequencies in database...")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for word, freq in word_frequencies.items():
        cursor.execute('''
            INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)
            ON CONFLICT(word) DO UPDATE SET frequency = frequency + ?
        ''', (word, freq, freq))
    conn.commit()
    log_message(db_name, "Word frequencies stored in database.")
    conn.close()

def create_word_frequencies_per_file(db_name: str) -> None:
    """Calculate and store word frequencies for each file from text chunks in the database."""
    
    if not db_name:
        raise ValueError("Database name cannot be empty")

    def clean_text(text: str) -> list[str]:
        """Clean and split text into words."""
        text = re.sub(r'[^a-zA-Z\s]', '', text).lower()
        words = text.split()
        return words

    def get_chunks_by_file(conn) -> dict[str, list[str]]:
        """Retrieve text chunks from the database grouped by file name."""
        cursor = conn.cursor()
        cursor.execute('SELECT file_name, chunk_text FROM pdf_chunks')
        file_chunks = defaultdict(list)
        for file_name, chunk_text in cursor.fetchall():
            file_chunks[file_name].append(chunk_text)
        return file_chunks

    def calculate_word_frequencies(file_chunks: dict[str, list[str]]) -> dict[str, dict[str, int]]:
        """Calculate word frequencies for each file."""
        file_word_frequencies = {}
        for file_name, chunks in file_chunks.items():
            word_frequencies = defaultdict(int)
            for chunk in chunks:
                words = clean_text(chunk)
                for word in words:
                    word_frequencies[word] += 1
            file_word_frequencies[file_name] = word_frequencies
        return file_word_frequencies

    def store_word_frequencies(conn, file_word_frequencies: dict[str, dict[str, int]]) -> None:
        """Store word frequencies in the database."""
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS word_frequencies_per_file (
                file_name TEXT NOT NULL,
                word TEXT NOT NULL,
                frequency INTEGER NOT NULL
            )
        ''')
        for file_name, word_freq in file_word_frequencies.items():
            for word, frequency in word_freq.items():
                cursor.execute('''
                    INSERT INTO word_frequencies_per_file (file_name, word, frequency) VALUES (?, ?, ?)
                    ON CONFLICT(file_name, word) DO UPDATE SET frequency = frequency + ?
                ''', (file_name, word, frequency, frequency))
        conn.commit()

    conn = sqlite3.connect(db_name)
    try:
        file_chunks = get_chunks_by_file(conn)
        file_word_frequencies = calculate_word_frequencies(file_chunks)
        store_word_frequencies(conn, file_word_frequencies)
    except sqlite3.Error as e:
        log_message(db_name, f"Database error: {e}")
    finally:
        conn.close()

    log_message(db_name, "Word frequencies per file have been calculated and stored in the database.")

def process_pdf_info_table(db_name: str) -> None:
    def get_page_count(file_name: str) -> int:
        """Get page count from the PDF file."""
        if not os.path.isfile(file_name):
            raise ValueError(f"File does not exist: {file_name}")
        if not file_name.endswith('.pdf'):
            raise ValueError(f"File is not a PDF: {file_name}")
        
        with fitz.open(file_name) as doc:
            return doc.page_count
    
    def get_primary_keys(file_name: str) -> list[str]:
        """Get primary keys from the file name."""
        return [word for word in file_name.split() if len(word) > 3]
    
    def get_secondary_keys(db_name: str) -> dict[str, list[str]]:
        """Get secondary keys from the word_frequencies_per_file table."""
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT file_name, word FROM word_frequencies_per_file')
        secondary_keys = defaultdict(list)
        for file_name, word in cursor.fetchall():
            secondary_keys[file_name].append(word)
        conn.close()
        return secondary_keys

    def get_note_list_corresponding_to_pdf(db_name: str) -> dict[str, list[str]]:
        """Get note list corresponding to each PDF file from the note_list table."""
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('SELECT file_name, note_name FROM note_list')
        note_list = defaultdict(list)
        for file_name, note_name in cursor.fetchall():
            note_list[file_name].append(note_name)
        conn.close()
        return note_list

    def store_pdf_info_in_table(db_name: str, pdf_info: dict[str, dict[str, list]]) -> None:
        """Store PDF info in the pdf_info table."""
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdf_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                primary_keys TEXT NOT NULL,
                secondary_keys TEXT NOT NULL,
                note_list TEXT NOT NULL
            )
        ''')
        
        for file_name, info in pdf_info.items():
            cursor.execute('''
                INSERT INTO pdf_info (file_name, page_count, primary_keys, secondary_keys, note_list)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                file_name,
                info['page_count'],
                ','.join(info['primary_keys']),
                ','.join(info['secondary_keys']),
                ','.join(info['note_list'])
            ))
        
        conn.commit()
        conn.close()

    # Main function logic
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT file_name FROM pdf_chunks')
    pdf_files = [row[0] for row in cursor.fetchall()]
    conn.close()

    secondary_keys = get_secondary_keys(db_name)
    note_list = get_note_list_corresponding_to_pdf(db_name)
    pdf_info = {}

    for file_name in pdf_files:
        try:
            page_count = get_page_count(file_name)
            primary_keys = get_primary_keys(file_name)
            file_secondary_keys = secondary_keys.get(file_name, [])
            file_note_list = note_list.get(file_name, [])
            
            pdf_info[file_name] = {
                'page_count': page_count,
                'primary_keys': primary_keys,
                'secondary_keys': file_secondary_keys,
                'note_list': file_note_list
            }
        except Exception as e:
            log_message(db_name, f"Error processing {file_name}: {e}")

    store_pdf_info_in_table(db_name, pdf_info)
    log_message(db_name, "PDF info has been processed and stored in the database.")

def update_data() -> None:
    """Update data by processing PDF files and note files."""
    db_name = path.DB_name
    chunk_size = 1000
    reset_db = True
    setup_database(db_name, reset_db)
    pdf_files = get_file_list(path.BOOKS_folder_path, ".pdf")
    process_files(pdf_files, db_name, chunk_size)
    note_files = get_file_list(path.StudyNote_folder_path, ".md")
    process_note_files(note_files, db_name)
    process_chunks_in_batches(db_name)
    create_word_frequencies_per_file(db_name)
    process_pdf_info_table(db_name)
