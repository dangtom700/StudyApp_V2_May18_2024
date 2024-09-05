import logging
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import markdown
import time
import re
from collections import defaultdict
import nltk
from nltk.corpus import stopwords
from math import sqrt
from nltk.stem import PorterStemmer
from os import walk
from os.path import getmtime, basename, join
from datetime import datetime
from modules.path import log_file_path, chunk_database_path
from collections.abc import Generator
from modules.updateLog import print_and_log
from functools import wraps

# One-time compiled
REPEATED_CHAR_PATTERN = re.compile(r"([a-zA-Z])\1{2,}")
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))

def has_repeats_regex(word):
    return bool(REPEATED_CHAR_PATTERN.search(word))

def clean_text(text):
    # Remove punctuation and convert to lowercase
    text = re.sub(r'[^\w\s]', '', text).lower()

    # Split text into tokens
    tokens = text.split()

    # Filter and process tokens in one step
    filtered_tokens = []
    for token in tokens:
        if len(token) > 1 and len(token) < 14 and token.isalpha():
            # Stem the token and check conditions
            root_word = stemmer.stem(token)
            if not has_repeats_regex(root_word):
                filtered_tokens.append(root_word)

    return filtered_tokens

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

# Retry decorator with configurable retries and delays
def retry_on_exception(retries=99, delay=5, retry_exceptions=(Exception,), log_message=None):
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
    logging.info(f"Extracting text from {pdf_file}...")
    text = ""
    try:
        doc = fitz.open(pdf_file)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            page_text = page.get_text()
            logging.debug(f"Extracted text from page {page_num} of {pdf_file}: {page_text[:50]}...")
            text += page_text
    except fitz.fitz_error as e:
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
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    try:
        operation(cursor, *args)
        conn.commit()
    finally:
        conn.close()

# Function to store text chunks in the SQLite database
def store_chunks_in_db(file_name, chunks, db_name):
    def _store_chunks(cursor, file_name, chunks):
        for index, chunk in enumerate(chunks):
            cursor.execute('''
                INSERT INTO pdf_chunks (file_name, chunk_index, chunk_text) VALUES (?, ?, ?)
            ''', (basename(file_name), index, chunk))
    
    execute_db_operation(db_name, _store_chunks, file_name, chunks)
    logging.info(f"Stored {len(chunks)} chunks for {file_name} in the database.")

# Function to extract, split, and store text from a PDF file
def extract_split_and_store_pdf(pdf_file, chunk_size, db_name):
    try:
        text = extract_text_from_pdf(pdf_file)
        if not text:
            logging.warning(f"No text extracted from {pdf_file}.")
            return
        chunks = split_text_into_chunks(text, chunk_size=chunk_size)
        if not chunks:
            logging.warning(f"No chunks created for {pdf_file}.")
            return
        store_chunks_in_db(pdf_file, chunks, db_name)
    except Exception as e:
        logging.error(f"Error processing {pdf_file}: {e}")

# Store text chunks in the SQLite database
def store_chunks_in_db(file_name, chunks, db_name):
    def _store_chunks(cursor, file_name, chunks):
        for index, chunk in enumerate(chunks):
            cursor.execute('''
                INSERT INTO pdf_chunks (file_name, chunk_index, chunk_text) VALUES (?, ?, ?)
            ''', (file_name, index, chunk))
    
    execute_db_operation(db_name, _store_chunks, file_name, chunks)
    logging.info(f"Stored {len(chunks)} chunks for {file_name} in the database.")

# Process multiple PDF files concurrently
def process_files_in_parallel(pdf_files, chunk_size, db_name):
    total_files = len(pdf_files)
    completed_files = 0

    with ThreadPoolExecutor() as executor:
        future_to_file = {executor.submit(extract_split_and_store_pdf, pdf_file, chunk_size, db_name): pdf_file for pdf_file in pdf_files}

        for future in as_completed(future_to_file):
            pdf_file = future_to_file[future]
            try:
                future.result()
                completed_files += 1
                logging.info(f"Completed {completed_files}/{total_files} files: {pdf_file}")
            except Exception as e:
                logging.error(f"Error processing {pdf_file}: {e}")

# Retrieve title IDs from the database
def get_title_ids(cursor: sqlite3.Cursor) -> list[str]:
    cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0")
    return [title[0] for title in cursor.fetchall()]

# Retrieve and clean text chunks for a single title
def retrieve_token_list(title_id: str, cursor: sqlite3.Cursor) -> list[str]:
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

# Process chunks in batches and store word frequencies (with retry logic for DB insertion)
def process_chunks_in_batches(cursor: sqlite3.Cursor) -> None:
    word_frequencies = defaultdict(int)
    title_ids = get_title_ids(cursor)

    for title_id in title_ids:
        try:
            token_list = retrieve_token_list(title_id, cursor)
            for token in token_list:
                word_frequencies[token] += 1
        except ValueError as e:
            logging.warning(f"Warning: {e}")

    @retry_on_exception(retries=999, delay=5, retry_exceptions=(sqlite3.OperationalError,), log_message="Database is locked during word frequency insertion")
    def insert_word_frequencies(cursor):
        cursor.executemany('''
            INSERT INTO word_frequencies (word, frequency) 
            VALUES (?, ?)
            ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency
        ''', word_frequencies.items())

    insert_word_frequencies(cursor)

# Batch collect files from folder
def batch_collect_files(folder_path: str, extension='.pdf', batch_size=100):
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

# Extract text from PDF files in batches and store in DB
def extract_text(FOLDER_PATH, CHUNK_SIZE, chunk_database_path):
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
    create_table()

    for pdf_batch in batch_collect_files(FOLDER_PATH, batch_size=100):
        process_files_in_parallel(pdf_batch, chunk_size=CHUNK_SIZE, db_name=chunk_database_path)

    logging.info("Processing complete: Extracting text from PDF files.")
    conn.close()

# Process word frequencies from chunks stored in DB
def process_word_frequencies_in_batches(chunk_database_path):
    conn = sqlite3.connect(chunk_database_path)
    cursor = conn.cursor()

    def create_table():
        cursor.execute("DROP TABLE IF EXISTS word_frequencies")
        cursor.execute("""CREATE TABLE word_frequencies (
            word TEXT PRIMARY KEY,
            frequency INTEGER)
        """)

    logging.info("Starting batch processing of chunks...")
    create_table()

    process_chunks_in_batches(cursor)
    conn.commit()
    conn.close()

    logging.info("Processing word frequencies complete.")

# Main function to precompute title vector
def precompute_title_vector(database_path: str) -> None:
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    # Function to create tables with dynamic columns
    def create_tables(title_ids: list[str]) -> None:
        cursor.execute("DROP TABLE IF EXISTS title_analysis")
        cursor.execute("DROP TABLE IF EXISTS title_normalized")
        
        # Create dynamic columns for each title
        columns_INT = ', '.join([f"T_{title_id} INTEGER DEFAULT 0" for title_id in title_ids])
        columns_REAL = ', '.join([f"T_{title_id} REAL DEFAULT 0.0" for title_id in title_ids])
        
        cursor.execute(f"""
            CREATE TABLE title_analysis (
                word TEXT PRIMARY KEY, 
                {columns_INT},
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        cursor.execute(f"""
            CREATE TABLE title_normalized (
                word TEXT PRIMARY KEY,
                {columns_REAL},
                FOREIGN KEY(word) REFERENCES coverage_analysis(word)
            )
        """)
        
        # Insert unique words into both tables
        cursor.execute("INSERT INTO title_analysis (word) SELECT DISTINCT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_normalized (word) SELECT DISTINCT word FROM coverage_analysis")

    # Multithreaded function to process title analysis
    def process_title_analysis(title_ids: list[str], words: list[str]) -> None:
        def _process_title(title_id: str):
            token_list = retrieve_token_list(title_id=title_id, cursor=cursor)
            word_counts = {word: token_list.count(word) for word in words if word in token_list}

            # Batch update the title_analysis table for this title
            update_data = [(count, word) for word, count in word_counts.items()]
            cursor.executemany(
                f"UPDATE title_analysis SET T_{title_id} = ? WHERE word = ?",
                update_data
            )
            conn.commit()

        with ThreadPoolExecutor() as executor:
            future_to_title = {executor.submit(_process_title, title_id): title_id for title_id in title_ids}
            for future in as_completed(future_to_title):
                title_id = future_to_title[future]  # Retrieve the corresponding title_id
                try:
                    future.result()  # Ensure exceptions are raised and handled
                except Exception as e:
                    logging.error(f"Error in processing title analysis for title ID {title_id}: {e}")

    # Multithreaded function to normalize vectors
    def normalize_vector(title_ids: list[str]) -> None:
        def _normalize_single_title(title_id: str):
            length = cursor.execute(f"SELECT SUM(T_{title_id} * T_{title_id}) FROM title_analysis").fetchone()[0]
            length = sqrt(length) if length else 1  # Avoid division by zero
            cursor.execute(f"""
                UPDATE title_normalized
                SET T_{title_id} = 
                    (SELECT T_{title_id} FROM title_analysis WHERE title_normalized.word = title_analysis.word) 
                    / (1 + {length})
            """)
            conn.commit()

        with ThreadPoolExecutor() as executor:
            future_to_title = {executor.submit(_normalize_single_title, title_id): title_id for title_id in title_ids}
        
            for future in as_completed(future_to_title):
                title_id = future_to_title[future]  # Retrieve the corresponding title_id
                try:
                    future.result()  # Ensure exceptions are raised and handled
                except Exception as e:
                    logging.error(f"Error in normalizing vector for title ID {title_id}: {e}")

    # Retrieve unique words from the coverage_analysis table
    def get_words() -> list[str]:
        cursor.execute("SELECT word FROM coverage_analysis")
        return [word[0] for word in cursor.fetchall()]

    # Retrieve title IDs from the database (reuse existing function)
    def get_title_ids() -> list[str]:
        cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0")
        return [title[0] for title in cursor.fetchall()]

    # Main flow
    try:
        title_ids = get_title_ids()
        words = get_words()
        
        print_and_log("Creating tables...")
        execute_db_operation(database_path, create_tables, title_ids)
        print_and_log("Finished creating tables.")
        
        print_and_log("Processing title analysis in parallel...")
        process_title_analysis(title_ids, words)
        print_and_log("Finished processing title analysis.")
        
        print_and_log("Normalizing vectors in parallel...")
        normalize_vector(title_ids)
        print_and_log("Finished normalizing vectors.")

    finally:
        conn.close()

def suggest_top_titles(database_path: str, prompt: str, top_n = 10):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    prompt = clean_text(prompt)

    cursor.execute("SELECT word FROM coverage_analysis")
    words = cursor.fetchall()
    words = {word[0]: 0 for word in words}

    for token in words.keys():
        words[token] = prompt.count(token)

    length_prompt = sqrt(sum([value * value for value in words.values()]))

    normalized_prompt = {key: value / length_prompt for key, value in words.items()}

    title_list = cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0").fetchall()
    # create an array of zeros
    title_list = {name[0]: 0 for name in title_list}

    # get non-zero keys
    key_list = [key for key, value in normalized_prompt.items() if value != 0]

    # get values
    for title in title_list.keys():
        for key in key_list:
            cursor.execute(f"SELECT T_{title} FROM title_normalized WHERE word = ?", (key,))
            title_list[title] += cursor.fetchone()[0] * normalized_prompt[key]

    top_10 = sorted(title_list.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Look up the name of the top 10 titles
    for title, score in top_10:
        cursor.execute("SELECT file_name FROM file_list WHERE id = ?", (title,))
        print(f"{score:.18f}: {title} - {cursor.fetchone()[0]}")

    conn.close()

def get_modification_time(file_path: str) -> tuple[str, int]:
    modification_time = getmtime(file_path)
    formatted_modification_time = datetime.fromtimestamp(modification_time).strftime('%a, %b %d, %Y, %H:%M:%S')
    epoch_time = int(modification_time)
    return (formatted_modification_time, epoch_time)

def setup_database(reset_db: bool, db_name: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    if reset_db:
        cursor.execute("DROP TABLE IF EXISTS file_list")
    cursor.execute("""CREATE TABLE IF NOT EXISTS file_list (
                       id TEXT PRIMARY KEY, 
                       file_name TEXT, 
                       file_path TEXT, 
                       file_type TEXT,
                       created_time TEXT, 
                       epoch_time INTEGER,
                       chunk_count INTEGER,
                       start_id INTEGER,
                       end_id INTEGER
                       )""")

    conn.commit()
    conn.close()

def create_unique_id(file_basename: str, epoch_time: int, chunk_count: int, starting_id: int) -> str:
    encoded_file_name = sum(ord(char) for char in file_basename)
    encoded_file_name ^= 65536
    encoded_file_name &= 0xFFFF
    encoded_time = (epoch_time & 0xFFFF) >> 1
    encoded_num = (chunk_count * starting_id) & 0xFFFF
    encoded_num <<= 1
    redundancy = encoded_file_name ^ encoded_time ^ encoded_num
    redundancy &= 0xFFFF
    unique_id = f"{encoded_file_name:04X}{encoded_time:04X}{encoded_num:04X}{redundancy:04X}"
    return unique_id

def count_chunk_for_each_title(cursor: sqlite3.Cursor, file_name: str) -> int:
    cursor.execute("SELECT COUNT(chunk_index) FROM pdf_chunks WHERE file_name = ?", (file_name,))
    chunk_count = cursor.fetchone()[0]
    return chunk_count

def get_starting_and_ending_ids(cursor: sqlite3.Cursor, file_name: str) -> tuple[int, int]:
    cursor.execute('''
        SELECT MIN(id) AS starting_id, MAX(id) AS ending_id
        FROM pdf_chunks
        WHERE file_name = ?;
    ''', (file_name,))
    result = cursor.fetchone()
    starting_id, ending_id = result
    return starting_id, ending_id

@retry_on_exception(retries=99, delay=5, log_message="Error inserting file metadata")
def insert_file_metadata(conn: sqlite3.Connection, file_data: tuple) -> None:
    with conn.cursor() as cursor:
        cursor.execute("""INSERT INTO file_list (
            id, 
            file_name, 
            file_path,
            file_type,
            created_time,
            epoch_time,
            chunk_count,
            start_id,
            end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", file_data)
    conn.commit()

def store_files_in_db(file_names: list[str], file_list: list[str], db_name: str, file_type: str) -> None:
    def prepare_file_data(file_name: str, file_path: str) -> tuple:
        created_time, epoch_time = get_modification_time(file_path)
        file_basename = basename(file_path)
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        chunk_count = count_chunk_for_each_title(cursor, file_name=file_basename)
        starting_id, ending_id = get_starting_and_ending_ids(cursor, file_name=file_basename)
        if starting_id is None or ending_id is None:
            starting_id = 0
            ending_id = 0
        hashed_data = create_unique_id(file_basename, epoch_time, chunk_count, starting_id)
        conn.close()
        return (hashed_data, file_name, file_path, file_type, created_time, epoch_time, chunk_count, starting_id, ending_id)

    with ThreadPoolExecutor() as executor:
        conn = sqlite3.connect(db_name)
        futures = {
            executor.submit(prepare_file_data, file_name, file_path): (file_name, file_path)
            for file_name, file_path in zip(file_names, file_list)
        }
        
        for future in as_completed(futures):
            file_name, file_path = futures[future]
            try:
                file_data = future.result()  # Get the prepared file data
                insert_file_metadata(conn, file_data)
                logging.info(f"Inserted file metadata for: {file_name}")
            except Exception as e:
                logging.error(f"Error inserting metadata for {file_name}: {e}")
        
        conn.close()

def extract_names(raw_list: list[str], extension: str) -> list[str]:
    return [basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

def create_type_index_table(collector_folder_list: list[str], extension_list: list[str]) -> None:
    print_and_log("Started creating file index.")
    
    setup_database(reset_db=True, db_name=chunk_database_path)
    
    print_and_log("Started storing files in database.")
    for collector_folder, extension in zip(collector_folder_list, extension_list):
        for file_batch in batch_collect_files(folder_path=collector_folder, extension=extension, batch_size=100):
            file_names = extract_names(file_batch, extension)
            store_files_in_db(file_names, file_batch, chunk_database_path, extension.removeprefix("."))
            print_and_log(f"Finished processing batch of {len(file_batch)} markdown files.")
    
    print_and_log("Finished processing markdown files.")
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

@retry_on_exception(retries=99, delay=10, log_message="Error storing chunks in database")
def store_text_note_in_chunks(file_name, chunks, db_name) -> None:
    """Stores chunks in the database."""
    store_chunks_in_db(file_name=file_name, chunks=chunks, db_name=db_name)

def process_markdown_file(file_path, chunk_size=800) -> None:
    """Processes a single markdown file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        for raw_chunk in extract_note_text_chunk(file):
            text = clean_markdown_text(raw_chunk)
            chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
            store_text_note_in_chunks(file_name=basename(file_path), chunks=chunks, db_name=chunk_database_path)

def process_markdown_file_with_retries(file_path: str, chunk_size: int) -> None:
    """Wraps the processing of a markdown file to handle retries."""
    retry_on_exception(retries=99, delay=10, log_message=f"Processing file {basename(file_path)}")(process_markdown_file)(file_path, chunk_size)

def process_text_note_batch_of_files(file_batch: list[str], chunk_size=800) -> None:
    """Processes a batch of markdown files concurrently."""
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_markdown_file_with_retries, file_path, chunk_size) for file_path in file_batch]
        for future in as_completed(futures):
            try:
                future.result()  # Ensure exceptions are raised and handled
            except Exception as e:
                logging.error(f"Error processing file batch: {e}")

def extract_markdown_notes_in_batches(directory, chunk_size=800) -> None:
    """Main process to collect, extract, chunk, and store markdown files in batches using multithreading."""
    for file_batch in batch_collect_files(folder_path=directory, extension='.md'):
        process_text_note_batch_of_files(file_batch, chunk_size=chunk_size)
        print_and_log(f"Finished processing batch of {len(file_batch)} markdown files.")

    print_and_log("Finished processing markdown files.")
