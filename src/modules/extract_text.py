import logging
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
import concurrent.futures
import threading
import markdown
import time
import re
from nltk.corpus import stopwords
from os import walk
from os.path import basename, join
from modules.path import log_file_path, chunk_database_path, pdf_path
from collections.abc import Generator
from modules.updateLog import print_and_log, log_message

# Setup logging to log messages to a file, with the option to reset the log file
def setup_logging(log_file= log_file_path):
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filemode='a'  # This will overwrite the log file each time the script runs
    )

setup_logging()

# Function to extract text from a PDF file using PyMuPDF with improved error handling
def extract_text_from_pdf(pdf_file):
    logging.info(f"Extracting text from {pdf_file}...")
    text = ""
    try:
        doc = fitz.open(pdf_file)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            logging.debug(f"Extracted text from page {page_num} of {pdf_file}: {page_text[:50]}...")  # Log first 50 characters for debugging
            text += page_text
    except fitz.fitz_error as e:  # Specific MuPDF error
        logging.error(f"MuPDF error in {pdf_file}: {e}")
    except Exception as e:
        logging.error(f"Error extracting text from {pdf_file}: {e}")
    finally:
        if 'doc' in locals():
            doc.close()
    logging.info(f"Finished extracting text from {pdf_file}.")
    return text

# Function to split text into chunks using LangChain
def split_text_into_chunks(text, chunk_size):
    logging.info(f"Splitting text into chunks of {chunk_size} characters...")
    if not isinstance(text, str):
        logging.error(f"Expected text to be a string but got {type(text)}: {text}")
        return []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
    try:
        chunks = text_splitter.split_text(text)
        logging.debug(f"First chunk of {text[:50]}...")  # Log first 50 characters of the first chunk
    except Exception as e:
        logging.error(f"Error splitting text: {e}")
        chunks = []
    logging.info(f"Finished splitting text into chunks.")
    return chunks

def execute_with_retry(func, *args, retries=999, delay=10, **kwargs):
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            if 'locked' in str(e):
                logging.warning(f"{attempt+1}/{retries} Database is locked, retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                raise
    raise Exception(f"Failed to execute after {retries} retries")

# Function to store text chunks in the SQLite database
def store_chunks_in_db(file_name, chunks, db_name):
    def _store():
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        for index, chunk in enumerate(chunks):
            cursor.execute('''
                INSERT INTO pdf_chunks (file_name, chunk_index, chunk_text) VALUES (?, ?, ?)
            ''', (basename(file_name), index, chunk))
        conn.commit()
        conn.close()
    execute_with_retry(_store)
    logging.info(f"Stored {len(chunks)} chunks for {file_name} in the database.")

# Function to split text into chunks using LangChain
def split_text_into_chunks(text, chunk_size):
    logging.info(f"Splitting text into chunks of {chunk_size} characters...")
    if not isinstance(text, str):
        logging.error(f"Expected text to be a string but got {type(text)}: {text}")
        return []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
    try:
        chunks = text_splitter.split_text(text)
        logging.debug(f"First chunk of {text[:50]}...")  # Log first 50 characters of the first chunk
    except Exception as e:
        logging.error(f"Error splitting text: {e}")
        chunks = []
    logging.info(f"Finished splitting text into chunks.")
    return chunks

# Function to extract, split, and store text from a PDF file
def extract_split_and_store_pdf(pdf_file, chunk_size, db_name):
    try:
        text = extract_text_from_pdf(pdf_file)
        if text is None or text == "":
            logging.warning(f"No text extracted from {pdf_file}.")
            return
        logging.debug(f"Extracted text type: {type(text)}, length: {len(text)}")
        chunks = split_text_into_chunks(text, chunk_size=chunk_size)
        if not chunks:
            logging.warning(f"No chunks created for {pdf_file}.")
            return
        store_chunks_in_db(pdf_file, chunks, db_name)
    except Exception as e:
        logging.error(f"Error processing {pdf_file}: {e}")

# Function to process multiple PDF files concurrently
def process_files_in_parallel(pdf_files, chunk_size, db_name):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_file = {executor.submit(extract_split_and_store_pdf, pdf_file, chunk_size, db_name): pdf_file for pdf_file in pdf_files}
        
        total_files = len(pdf_files)
        completed_files = 0

        for future in concurrent.futures.as_completed(future_to_file):
            pdf_file = future_to_file[future]
            try:
                future.result()
                completed_files += 1
                logging.info(f"Completed {completed_files}/{total_files} file: {pdf_file}")
            except Exception as e:
                logging.error(f"Error processing {pdf_file}: {e}")

def batch_collect_files(folder_path: str, extension='.pdf', batch_size=100) -> Generator[list[str], None, None]:
    """
    Generator function that yields batches of files from the specified folder.

    :param folder_path: Path to the folder containing the files.
    :param extensions: File extension to filter by (default is '.pdf').
    :param batch_size: Number of files to include in each batch (default is 100).
    :yield: List of file paths.
    """
    current_batch = []

    for root, _, files in walk(folder_path):
        for file in files:
            if file.lower().endswith(extension):
                current_batch.append(join(root, file))
                if len(current_batch) == batch_size:
                    yield current_batch
                    current_batch = []

    # Yield any remaining files in the last batch
    if current_batch:
        yield current_batch

def extract_text(FOLDER_PATH = pdf_path, CHUNK_SIZE = 800) -> None:
    conn = sqlite3.connect(chunk_database_path)
    def create_table():
        conn.execute("DROP TABLE IF EXISTS pdf_chunks")
        conn.execute("""CREATE TABLE pdf_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            chunk_index INTEGER,
            chunk_text TEXT)
        """)

    logging.info(f"Starting processing of PDF files in batches...")
    print(f"Starting processing of PDF files in batches...")

    create_table()

    num_files = 0
    for pdf_batch in batch_collect_files(FOLDER_PATH, batch_size=100):
        num_files += len(pdf_batch)
        print(f"Processing {num_files} files...")
        process_files_in_parallel(pdf_batch, chunk_size=CHUNK_SIZE, db_name=chunk_database_path)

    logging.info("Processing complete: Extracting text from PDF files.")
    print("Processing complete: Extracting text from PDF files.")

def extract_note_text_chunk(file, chunk_size=4000) -> Generator[str, None, None]:
    """Extracts and cleans text chunk by chunk from a markdown file."""
    content = []
    for line in file:
        content.append(line)
        if sum(len(c) for c in content) >= chunk_size:
            yield ''.join(content)
            content = []
    
    if content:
        yield ''.join(content)

def clean_markdown_text(markdown_text) -> str:
    """Converts markdown text to plain text by removing HTML tags."""
    html_content = markdown.markdown(markdown_text)
    text = re.sub(r'<[^>]+>', '', html_content)
    return text

def store_text_note_in_chunks_with_retry(file_name, chunks, db_name, MAX_RETRIES = 999, RETRY_DELAY = 10) -> None:
    """Stores chunks in the database with retry logic."""
    attempts = 0
    while attempts < MAX_RETRIES:
        try:
            store_chunks_in_db(file_name=file_name, chunks=chunks, db_name=db_name)
            break  # If successful, break out of the loop
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                attempts += 1
                time.sleep(RETRY_DELAY)
                continue
            else:
                raise  # Raise other SQLite exceptions
        except Exception as e:
            print(f"Error while storing chunks: {e}")
            raise  # Raise any other exceptions
    else:
        print(f"Failed to store chunks after {MAX_RETRIES} attempts for file {file_name}")

def process_markdown_file(file_path, CHUNK_SIZE = 800) -> None:
    """Processes a single markdown file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        for raw_chunk in extract_note_text_chunk(file):
            text = clean_markdown_text(raw_chunk)
            chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
            store_text_note_in_chunks_with_retry(file_name=basename(file_path), chunks=chunks, db_name=chunk_database_path)

def process_text_note_batch_of_files(file_batch: list[str], chunk_size = 800) -> None:
    """Processes a batch of markdown files concurrently."""
    threads = []
    
    for file_path in file_batch:
        thread = threading.Thread(target=process_markdown_file, args=(file_path,chunk_size,))
        thread.start()
        threads.append(thread)
    
    for thread in threads:
        thread.join()  # Wait for all threads in the batch to finish

def extract_markdown_notes_in_batches(directory, chunk_size = 800) -> None:
    """Main process to collect, extract, chunk, and store markdown files in batches using multithreading."""
    for file_batch in batch_collect_files(folder_path=directory, extension='.md'):
        process_text_note_batch_of_files(file_batch, chunk_size=chunk_size)
        print_and_log(f"Finished processing batch of {len(file_batch)} markdown files.")

    print_and_log("Finished processing markdown files.")
