import logging
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from os import walk
import re
from os.path import basename, join
from modules.path import log_file_path
from collections.abc import Generator

# Setup logging to log messages to a file, with the option to reset the log file
def setup_logging(log_file= log_file_path):
    """Setup logging to log messages to a file, with the option to reset the log file.
    
    Args:
        log_file (str): The path to the log file. If not specified, defaults to the path in `modules.path`.
    """
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s;%(levelname)s;%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        filemode='a'  # This will overwrite the log file each time the script runs
    )

setup_logging()

# Retry decorator with configurable retries and delays
def retry_on_exception(retries=99, delay=5, retry_exceptions=(Exception,), log_message=None):
    """A decorator that retries a function on exceptions, with configurable retries and delays.

    Args:
        retries (int): The number of times to retry the function. Defaults to 99.
        delay (int): The number of seconds to wait between retries. Defaults to 5.
        retry_exceptions (tuple): A tuple of exceptions to catch and retry on. Defaults to (Exception,).
        log_message (str): An optional message to log before retrying. Defaults to None.

    Returns:
        A decorator that wraps the function in a retry loop.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except retry_exceptions as e:
                    if attempt < retries - 1:
                        if log_message:
                            logging.warning(f"{log_message}. Attempt {attempt + 1}/{retries}, retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        raise
        return wrapper
    return decorator

# Function to extract text from a PDF file
def extract_text_from_pdf(pdf_file):
    """Extract text from a PDF file using MuPDF.

    Args:
        pdf_file (str): The path to the PDF file.

    Returns:
        str: The extracted text from the PDF file.
    """
    text = ""
    try:
        doc = fitz.open(pdf_file)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            logging.debug(f"Extracted text from page {page_num} of {pdf_file}: {page_text[:50]}...")
            text += page_text
    except Exception as e:
        logging.error(f"MuPDF error in {pdf_file}: {e}")
    except Exception as e:
        logging.error(f"Error extracting text from {pdf_file}: {e}")
    finally:
        if 'doc' in locals():
            doc.close()
    logging.info(f"Finished extracting text from {pdf_file}.")
    return text

# Function to split text into chunks
def split_text_into_chunks(text, chunk_size):
    """Split text into chunks of a specified size.

    Args:
        text (str): The text to split into chunks.
        chunk_size (int): The size of each chunk in characters.

    Returns:
        list: A list of strings, where each string is a chunk of the input text.
    """
    logging.info(f"Splitting text into chunks of {chunk_size} characters...")
    if not isinstance(text, str):
        logging.error(f"Expected text to be a string but got {type(text)}: {text}")
        return []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
    try:
        chunks = text_splitter.split_text(text)
        logging.debug(f"First chunk: {chunks[0][:50]}..." if chunks else "No chunks.")
    except Exception as e:
        logging.error(f"Error splitting text: {e}")
        chunks = []
    logging.info("Finished splitting text into chunks.")
    return chunks

# Reusable database operation with retry logic
@retry_on_exception(retries=999, delay=5, retry_exceptions=(sqlite3.OperationalError,), log_message="Database is locked")
def execute_db_operation(db_name, operation, *args):
    """A reusable database operation with retry logic to handle OperationalErrors (i.e. "Database is locked").
    
    Args:
        db_name (str): The name of the database to connect to.
        operation (function): A function that takes a cursor and variable arguments, and performs a database operation.
        *args: Any additional arguments to pass to the operation function.
    
    Returns:
        None
    """
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    try:
        operation(cursor, *args)
        conn.commit()
    finally:
        conn.close()

def ultra_clean_token(text):
    """Perform ultra cleaning on a given string by removing leading/trailing spaces, 
    newlines, special characters, and extra spaces. This is a more aggressive 
    version of the clean_text function.

    Parameters
    ----------
    text : str
        The string to be cleaned.

    Returns
    -------
    str
        The cleaned string.
    """
    text = text.strip() # Remove leading/trailing spaces
    text = re.sub(r"\n", " ", text) # Remove newlines
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text) # Remove special characters
    text = re.sub(r"\s+", " ", text) # Remove extra spaces
    return text

# Function to extract, split, and store text from a PDF file
def extract_split_and_store_pdf(pdf_file, chunk_size, db_name):
    """Extract text from a PDF file using MuPDF, split the text into chunks of the given size, clean the chunks using ultra_clean_token, and store the chunks in the SQLite database.

    Args:
        pdf_file (str): The path to the PDF file.
        chunk_size (int): The size of each chunk in characters.
        db_name (str): The name of the database to connect to.

    Returns:
        None
    """
    try:
        text = extract_text_from_pdf(pdf_file)
        if not text:
            logging.warning(f"No text extracted from {pdf_file}.")
            return
        chunks = split_text_into_chunks(text, chunk_size=chunk_size)
        chunks = [ultra_clean_token(chunk) for chunk in chunks]
        if not chunks:
            logging.warning(f"No chunks created for {pdf_file}.")
            return
        store_chunks_in_db(pdf_file, chunks, db_name)
    except Exception as e:
        logging.error(f"Error processing {pdf_file}: {e}")

# Store text chunks in the SQLite database
def store_chunks_in_db(file_name, chunks, db_name):
    """
    Store text chunks in the SQLite database.

    This function takes a file name, a list of text chunks, and a database name,
    and stores the text chunks in the `pdf_chunks` table of the SQLite database.
    Each chunk is associated with the file name and its index within the file.

    Args:
        file_name (str): The name of the file from which the chunks were extracted.
        chunks (list): A list of text chunks to be stored in the database.
        db_name (str): The name of the SQLite database to connect to.

    Returns:
        None
    """

    def _store_chunks(cursor, file_name, chunks):
        for index, chunk in enumerate(chunks):
            cursor.execute('''
                INSERT INTO pdf_chunks (file_name, chunk_index, chunk_text) VALUES (?, ?, ?)
            ''', (file_name, index, chunk))
    
    execute_db_operation(db_name, _store_chunks, file_name, chunks)
    logging.info(f"Stored {len(chunks)} chunks for {file_name} in the database.")

# Process multiple PDF files concurrently
def process_files_in_parallel(pdf_files: list[str], chunk_size: int, db_name: str) -> None:

    """
    Process multiple PDF files concurrently in batches.

    This function takes a list of PDF file paths, a chunk size, and a database name,
    and processes each PDF file in parallel using ThreadPoolExecutor. For each PDF file,
    it extracts text using `extract_text_from_pdf`, splits the text into chunks of the given size
    using `split_text_into_chunks`, and stores the chunks in the `pdf_chunks` table of the SQLite
    database using `store_chunks_in_db`.

    Args:
        pdf_files (list[str]): A list of PDF file paths to be processed.
        chunk_size (int): The size of each chunk in characters.
        db_name (str): The name of the SQLite database to connect to.

    Returns:
        None
    """
    with ThreadPoolExecutor() as executor:
        future_to_file = {executor.submit(extract_split_and_store_pdf, pdf_file, chunk_size, db_name): pdf_file for pdf_file in pdf_files}

        for future in as_completed(future_to_file):
            pdf_file = future_to_file[future]
            try:
                future.result()
                logging.info(f"Processed {pdf_file}")
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

    if current_batch:
        yield current_batch

def extract_text(FOLDER_PATH, CHUNK_SIZE, chunk_database_path, reset_db):
    """Extracts text from PDF files in batches and stores them in a database."""
    
    def create_table(conn):
        """Creates or resets the database table."""
        conn.execute("DROP TABLE IF EXISTS pdf_chunks")
        conn.execute("""CREATE TABLE pdf_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            chunk_index INTEGER,
            chunk_text TEXT)
        """)

    def fetch_existing_files(conn):
        """Fetches file names already stored in the database."""
        try:
            return {row[0] for row in conn.execute("SELECT DISTINCT file_name FROM pdf_chunks")}
        except sqlite3.OperationalError as e:
            logging.warning(f"Database error: {e}")
            return set()

    def list_pdf_files(folder_path):
        """Lists all PDF files in the given folder."""
        return {join(root, file) for root, _, files in walk(folder_path) for file in files if file.endswith('.pdf')}

    logging.info("Starting processing of PDF files...")

    with sqlite3.connect(chunk_database_path) as conn:
        if reset_db:
            create_table(conn)
            pdf_to_process = list_pdf_files(FOLDER_PATH)
        else:
            existing_files = fetch_existing_files(conn)
            all_files = list_pdf_files(FOLDER_PATH)
            pdf_to_process = all_files - existing_files
        
        logging.info(f"Found {len(pdf_to_process)} new PDF files to process.")

        if pdf_to_process:
            process_files_in_parallel(list(pdf_to_process), chunk_size=CHUNK_SIZE, db_name=chunk_database_path)
        else:
            logging.info("No new PDF files to process.")

    logging.info("Processing complete.")
