import os
import sqlite3
import concurrent.futures
import time
import fitz  # PyMuPDF
from langchain import RecursiveCharacterTextSplitter

import modules.path as path


def get_file_list(folder_path: str, file_type: str) -> list[str]:
    """Get list of files in a folder with a specific file type."""
    if not os.path.isdir(folder_path):
        raise ValueError(f"The provided folder path does not exist: {folder_path}")
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(file_type)]


def setup_database(db_name: str, reset_db: bool) -> None:
    """Set up the database for storing PDF chunks and word frequencies."""
    if not db_name:
        raise ValueError("Database name cannot be empty")
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    if reset_db:
        cursor.execute('DROP TABLE IF EXISTS pdf_chunks')
        cursor.execute('DROP TABLE IF EXISTS log')
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
    except fitz.fitz_error as e:  # Specific MuPDF error
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
    while attempt < 999 and not success:
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


def extractPDFindexFromTable(db_name: str) -> None:
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
        while attempt < 999 and not success:
            try:
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM note_list')
                if cursor.fetchone():
                    log_message(db_name, "Skipping store_data_in_note_table because the table is not empty.")
                    return
                conn.close()
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()
                cursor.executemany('''
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
