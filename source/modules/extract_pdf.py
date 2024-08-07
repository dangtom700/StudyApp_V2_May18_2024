import logging
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
import concurrent.futures
import time
import os
import re
from collections import defaultdict
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from modules.path import log_file_path, chunk_database_path, pdf_path

stemmer = PorterStemmer()
def has_repeats_regex(word, n=3):
    pattern = f"([a-zA-Z])\\1{{{n - 1}}}"
    return bool(re.search(pattern, word))
# Function to clean the text by removing non-alphabetic characters and converting to lowercase
def clean_text(text):
    def pass_conditions(word):
        alphabetic = word.isalpha()
        non_repeating = not has_repeats_regex(word)
        len_pass = len(word) < 12
        return alphabetic and non_repeating and len_pass
    """Preprocesses text by lowercasing, removing punctuation, and stop words."""
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    tokens = text.split()
    stop_words = set(stopwords.words('english'))
    tokens = [w for w in tokens if not w in stop_words]
    tokens = [stemmer.stem(item) for item in tokens if pass_conditions(item)]
    return tokens

def download_nltk():
    print("Downloading NLTK resources...")
    nltk.download('punkt')
    nltk.download('stopwords')
    print("NLTK resources downloaded.")

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

# Setup the SQLite database and create the table, optionally dropping the existing table if it exists
def setup_database(db_name, reset_db, action: str):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    if reset_db and action == "extract_text":
        cursor.execute('DROP TABLE IF EXISTS pdf_chunks')
    if action == "extract_text":
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdf_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL
            )
        ''')
    if reset_db and action == "word_frequency":
        cursor.execute('DROP TABLE IF EXISTS word_frequencies')
    if action == "word_frequency":
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS word_frequencies (
                word TEXT PRIMARY KEY,
                frequency INTEGER
            )
        ''')
    conn.commit()
    conn.close()

# Function to execute a database operation with a retry mechanism
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
            ''', (os.path.basename(file_name), index, chunk))
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
def process_files_in_parallel(pdf_files, reset_db, chunk_size, db_name):
    setup_database(db_name, reset_db, action="extract_text")  # Ensure the database is reset before processing files
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
                print(f"Completed {completed_files}/{total_files}={completed_files/total_files:.2%} file: {os.path.basename(pdf_file).removesuffix('.pdf')}")
            except Exception as e:
                logging.error(f"Error processing {pdf_file}: {e}")

# Batch processing for merging chunks and cleaning text
def process_chunks_in_batches(db_name: str, batch_size=100):

    # Function to retrieve chunks in batches
    def retrieve_chunks_in_batches():
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pdf_chunks")
        total_chunks = cursor.fetchone()[0]
        for offset in range(0, total_chunks, batch_size):
            cursor.execute("SELECT chunk_text FROM pdf_chunks ORDER BY id LIMIT ? OFFSET ?", (batch_size, offset))
            yield [row[0] for row in cursor.fetchall()]
            # print(f"Retrived {batch_size + offset} chunks")
        conn.close()

    # Function to merge split words in the chunks
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

    # Dictionary to store word frequencies
    word_frequencies = defaultdict(int)

    # Retrieve and process chunks in batches
    for chunk_batch in retrieve_chunks_in_batches():
        merged_chunks = merge_split_words(chunk_batch)
        for chunk in merged_chunks:
            cleaned_words = clean_text(chunk)
            for word in cleaned_words:
                word_frequencies[word] += 1

    # Store word frequencies in database
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    for word, freq in word_frequencies.items():
        cursor.execute('''
            INSERT INTO word_frequencies (word, frequency) VALUES (?, ?)
            ON CONFLICT(word) DO UPDATE SET frequency = frequency + ?
        ''', (word, freq, freq))
    conn.commit()
    conn.close()

# Main function
def extract_text() -> None:
    FOLDER_PATH = pdf_path
    CHUNK_SIZE = 800
    RESET_DATABASE = True
    DB_NAME = chunk_database_path

    pdf_files = [os.path.join(FOLDER_PATH, file) for file in os.listdir(FOLDER_PATH) if file.lower().endswith('.pdf')]
    
    # Reset the database before processing
    setup_database(reset_db=RESET_DATABASE, db_name=DB_NAME, action="extract_text")
    
    logging.info(f"Starting processing of {len(pdf_files)} PDF files...")
    print(f"Starting processing of {len(pdf_files)} PDF files...")
    process_files_in_parallel(pdf_files, reset_db=RESET_DATABASE, chunk_size=CHUNK_SIZE, db_name=DB_NAME)
    logging.info("Processing complete: Extracting text from PDF files.")
    print("Processing complete: Extracting text from PDF files.")

def process_word_frequencies_in_batches():
    # Now process the chunks in batches and store word frequencies
    setup_database(reset_db=True, db_name=chunk_database_path, action="word_frequency")
    logging.info("Starting batch processing of chunks...")
    process_chunks_in_batches(db_name=chunk_database_path)
    logging.info("Processing word frequencies complete.")
    print("Processing word frequencies complete.")
