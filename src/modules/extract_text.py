import logging
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
import sqlite3
import concurrent.futures
import threading
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
from modules.path import log_file_path, chunk_database_path, pdf_path
from collections.abc import Generator
from modules.updateLog import print_and_log, log_message

# One time complied
REPEATED_CHAR_PATTERN = re.compile(r"([a-zA-Z])\1{2,}")
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))

def has_repeats_regex(word, n=3):
    return bool(REPEATED_CHAR_PATTERN.search(word))

def clean_text(text):
    # Remove punctuation and convert to lowercase
    text = re.sub(r'[^\w\s]', '', text).lower()

    # Split text into tokens
    tokens = text.split()

    # Define a function to filter tokens
    def pass_conditions(word):
        return (len(word) < 12 and
                len(word) > 1 and
                word.isalpha() and 
                not has_repeats_regex(word))

    # Filter tokens based on conditions and apply stemming
    filtered_tokens = [stemmer.stem(token) for token in tokens
                       if token not in stop_words and pass_conditions(token)]

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

# Process chunks in batches and store word frequencies
def process_chunks_in_batches(db_name: str):
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()

        word_frequencies = defaultdict(int)
        title_ids = get_title_ids(cursor)

        for title_id in title_ids:
            try:
                token_list = retrieve_token_list(title_id, cursor)
                for token in token_list:
                    word_frequencies[token] += 1
            except ValueError as e:
                print(f"Warning: {e}")

        # Efficiently insert word frequencies into the database
        cursor.executemany('''
            INSERT INTO word_frequencies (word, frequency) 
            VALUES (?, ?)
            ON CONFLICT(word) DO UPDATE SET frequency = frequency + excluded.frequency
        ''', word_frequencies.items())

        conn.commit()

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

def process_word_frequencies_in_batches():
    conn = sqlite3.connect(chunk_database_path)
    cursor = conn.cursor()

    def create_table():
        cursor.execute("DROP TABLE IF EXISTS word_frequencies")
        cursor.execute("""CREATE TABLE word_frequencies (
            word TEXT PRIMARY KEY,
            frequency INTEGER)
        """)

    create_table()

    logging.info("Starting batch processing of chunks...")
    process_chunks_in_batches(db_name=chunk_database_path)
    logging.info("Processing word frequencies complete.")
    print("Processing word frequencies complete.")

def precompute_title_vector(database_path: str) -> None:
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    def create_tables(title_ids: list) -> None:
        cursor.execute("DROP TABLE IF EXISTS title_analysis")
        cursor.execute("DROP TABLE IF EXISTS title_normalized")
        # Create command strings for columns
        columns_INT = ', '.join([f"T_{title_id} INTEGER DEFAULT 0" for title_id in title_ids])
        columns_REAL = ', '.join([f"T_{title_id} REAL DEFAULT 0.0" for title_id in title_ids])
        
        # Create the tables with the necessary columns
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

        # Insert words into tables
        cursor.execute("INSERT INTO title_analysis (word) SELECT DISTINCT word FROM coverage_analysis")
        cursor.execute("INSERT INTO title_normalized (word) SELECT DISTINCT word FROM coverage_analysis")

    def process_title_analysis(title_ids: list[str], words: list[str], cursor: sqlite3.Cursor) -> None:
        for title in title_ids:
            token_list = retrieve_token_list(title_id=title, cursor=cursor)
            word_counts = {word: token_list.count(word) for word in words if word in token_list}

            # Batch update the title_analysis table
            update_data = [(count, word) for word, count in word_counts.items()]
            cursor.executemany(
                f"UPDATE title_analysis SET T_{title} = ? WHERE word = ?",
                update_data
            )
        conn.commit()

    def normalize_vector(title_ids: list[str]) -> None:
        for title in title_ids:
            length = cursor.execute(f"SELECT SUM(T_{title} * T_{title}) FROM title_analysis").fetchone()[0]
            length = sqrt(length)
            cursor.execute(f"""
                UPDATE title_normalized
                    SET T_{title} = 
                        (SELECT T_{title} FROM title_analysis WHERE title_normalized.word = title_analysis.word) /(1 + {length})""")
            conn.commit()

    def get_words() -> list[str]:
        cursor.execute("SELECT word FROM coverage_analysis")
        return [word[0] for word in cursor.fetchall()]

    # Main flow

    title_ids = get_title_ids(cursor=cursor)
    words = get_words()
    
    print_and_log("Creating tables...")
    create_tables(title_ids=title_ids)
    print_and_log("Finished creating tables.")
    
    print_and_log("Processing title analysis...")
    process_title_analysis(title_ids=title_ids, words=words, cursor=cursor)
    print_and_log("Finished processing title analysis.")
    
    print_and_log("Normalizing vectors...")
    normalize_vector(title_ids=title_ids)
    print_and_log("Finished normalizing vectors.")

    conn.commit()
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
    # Get the modification time in seconds since EPOCH
    modification_time = getmtime(file_path)
    # Convert the modification time to a recognizable timestamp
    formatted_modification_time = datetime.fromtimestamp(modification_time).strftime('%a, %b %d, %Y, %H:%M:%S')
    epoch_time = int(modification_time)
    return (formatted_modification_time, epoch_time)

def setup_database(reset_db: bool, db_name: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    if reset_db:
        cursor.execute(f"DROP TABLE IF EXISTS file_list")
    cursor.execute(f"""CREATE TABLE IF NOT EXISTS file_list (
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
    # Step 1: Encode the file basename
    # Sum the ASCII values of all characters, XOR by 1600, and apply & 0xFFFF
    encoded_file_name = sum(ord(char) for char in file_basename)
    encoded_file_name ^= 65536
    encoded_file_name &= 0xFFFF

    # Step 2: Encode the epoch time
    # Apply & 0xFFFF, then shift right by 1
    encoded_time = (epoch_time & 0xFFFF) >> 1

    # Step 3: Encode the chunk count and starting ID
    # Multiply, apply & 0xFFFF, then shift left by 1
    encoded_num = (chunk_count * starting_id) & 0xFFFF
    encoded_num <<= 1

    # Step 4: Add redundancy bits
    redundancy = encoded_file_name ^ encoded_time ^ encoded_num
    redundancy &= 0xFFFF

    # Step 4: Combine the results into a unique ID
    unique_id = f"{encoded_file_name:04X}{encoded_time:04X}{encoded_num:04X}{redundancy:04X}"

    return unique_id

def count_chunk_for_each_title(cursor: sqlite3.Cursor, file_name: str) -> int:
    cursor.execute(f"SELECT COUNT(chunk_index) FROM pdf_chunks WHERE file_name = ?", (file_name,))
    chunk_count = cursor.fetchone()[0]
    # print(f"Chunk count for {file_name}: {chunk_count}")
    return chunk_count

def get_starting_and_ending_ids(cursor: sqlite3.Cursor, file_name: str) -> tuple[int, int]:
    # Execute a single query to get both the starting and ending IDs
    cursor.execute('''
        SELECT MIN(id) AS starting_id, MAX(id) AS ending_id
        FROM pdf_chunks
        WHERE file_name = ?;
    ''', (file_name,))
    
    result = cursor.fetchone()
    
    starting_id, ending_id = result
    # print(f"Starting ID: {starting_id}, Ending ID: {ending_id}")
    return starting_id, ending_id

def store_files_in_db(file_names: list[str], file_list: list[str], db_name: str, file_type: str) -> None:
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    for file_name, file_path in zip(file_names, file_list):
        created_time, epoch_time = get_modification_time(file_path)
        file_basename = basename(file_path)
        chunk_count = count_chunk_for_each_title(cursor, file_name=file_basename)
        starting_id, ending_id = get_starting_and_ending_ids(cursor, file_name=file_basename)
        if starting_id is None or ending_id is None:
            starting_id = 0
            ending_id = 0
        hashed_data = create_unique_id(file_basename, epoch_time, chunk_count, starting_id)
        
        cursor.execute(f"""INSERT INTO file_list (
            id, 
            file_name, 
            file_path,
            file_type,
            created_time,
            epoch_time,
            chunk_count,
            start_id,
            end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (hashed_data, file_name, file_path, file_type, created_time, epoch_time, chunk_count, starting_id, ending_id)
        )
    conn.commit()
    conn.close()
# Main function
def extract_names(raw_list: list[str], extension: list[str]) -> list[str]:
    return [basename(file).removesuffix(extension) for file in raw_list if file.endswith(extension)]

def create_type_index_table(collector_folder_list: list[str], extension_list: list[str]) -> None:
    print_and_log(f"Started creating file index.")
    
    # Initialize database
    setup_database(reset_db=True, db_name=chunk_database_path)
    
    print_and_log("Started storing files in database.")
    for collector_folder, extension in zip(collector_folder_list, extension_list):
        for file_batch in batch_collect_files(folder_path=collector_folder, extension=extension, batch_size=100):
            file_names = extract_names(file_batch, extension)
            
            for file_name, file_path_with_extension in zip(file_names, file_batch):
                log_message(f"Processing file: {file_name}...")
                store_files_in_db(file_names=[file_name], 
                                  file_list=[file_path_with_extension], 
                                  db_name=chunk_database_path, 
                                  file_type=extension.removeprefix("."))

    print_and_log(f"Files: file stored in database.")
    print_and_log(f"Processing complete: create file index.")

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
