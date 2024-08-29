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
from math import sqrt, log
from nltk.stem import PorterStemmer
from modules.path import log_file_path, chunk_database_path, pdf_path
from collections.abc import Generator
from modules.updateLog import log_message, print_and_log

stemmer = PorterStemmer()

# Compile the regex pattern once and reuse it
REPEATED_CHAR_PATTERN = re.compile(r"([a-zA-Z])\1{2,}")

def has_repeats_regex(word, n=3):
    """
    Check if the word contains any repeated characters more than n times.
    """
    return bool(REPEATED_CHAR_PATTERN.search(word))

def clean_text(text):
    """
    Preprocesses text by lowercasing, removing punctuation, and filtering out stop words and tokens with repeating characters.
    """
    # Initialize stemmer and stop words set once
    stemmer = PorterStemmer()
    stop_words = set(stopwords.words('english'))

    # Remove punctuation and convert to lowercase
    text = re.sub(r'[^\w\s]', '', text).lower()

    # Split text into tokens
    tokens = text.split()

    # Define a function to filter tokens
    def pass_conditions(word):
        return (len(word) < 12 and
                word.isalpha() and not has_repeats_regex(word))

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
                print(f"Completed {completed_files}/{total_files} file: {os.path.basename(pdf_file).removesuffix('.pdf')}")
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

# Main function
def batch_collect_files(folder_path: str, extension='.pdf', batch_size=100) -> Generator[list[str], None, None]:
    """
    Generator function that yields batches of files from the specified folder.

    :param folder_path: Path to the folder containing the files.
    :param extensions: File extension to filter by (default is '.pdf').
    :param batch_size: Number of files to include in each batch (default is 100).
    :yield: List of file paths.
    """
    current_batch = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(extension):
                current_batch.append(os.path.join(root, file))
                if len(current_batch) == batch_size:
                    yield current_batch
                    current_batch = []

    # Yield any remaining files in the last batch
    if current_batch:
        yield current_batch

def extract_text(FOLDER_PATH = pdf_path, CHUNK_SIZE = 800) -> None:
    # Initialize database, constants parameters
    RESET_DATABASE = True
    DB_NAME = chunk_database_path

    # Reset the database before processing
    setup_database(reset_db=RESET_DATABASE, db_name=DB_NAME, action="extract_text")
    
    logging.info(f"Starting processing of PDF files in batches...")
    print(f"Starting processing of PDF files in batches...")

    for pdf_batch in batch_collect_files(FOLDER_PATH, batch_size=100):
        process_files_in_parallel(pdf_batch, reset_db=RESET_DATABASE, chunk_size=CHUNK_SIZE, db_name=DB_NAME)

    logging.info("Processing complete: Extracting text from PDF files.")
    print("Processing complete: Extracting text from PDF files.")

def process_word_frequencies_in_batches():
    # Now process the chunks in batches and store word frequencies
    setup_database(reset_db=True, db_name=chunk_database_path, action="word_frequency")
    logging.info("Starting batch processing of chunks...")
    process_chunks_in_batches(db_name=chunk_database_path)
    logging.info("Processing word frequencies complete.")
    print("Processing word frequencies complete.")

def precompute_title_vector(database_name: str) -> None:
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    
    # def create_tables(title_ids: list) -> None:
    #     cursor.execute("DROP TABLE IF EXISTS title_analysis")
    #     cursor.execute("DROP TABLE IF EXISTS title_normalized")
    #     cursor.execute("DROP TABLE IF EXISTS title_tf_idf")

    #     # Create title_analysis and title_normalized tables
    #     cursor.execute("""
    #         CREATE TABLE title_analysis (
    #             word TEXT PRIMARY KEY, 
    #             FOREIGN KEY(word) REFERENCES coverage_analysis(word)
    #         )
    #     """)
    #     cursor.execute("""
    #         CREATE TABLE title_normalized (
    #             word TEXT PRIMARY KEY, 
    #             FOREIGN KEY(word) REFERENCES coverage_analysis(word)
    #         )
    #     """)
        
    #     for title_id in title_ids:
    #         cursor.execute(f"ALTER TABLE title_analysis ADD COLUMN 'title_{title_id}' INTEGER DEFAULT 0")
    #         cursor.execute(f"ALTER TABLE title_normalized ADD COLUMN 'title_{title_id}' REAL DEFAULT 0.0")

    #     # Create title_tf_idf table with the same structure as title_normalized
    #     cursor.execute("CREATE TABLE title_tf_idf AS SELECT * FROM title_normalized WHERE 1 = 0")

    #     # Insert words into title_analysis and title_normalized
    #     cursor.execute("INSERT INTO title_analysis (word) SELECT DISTINCT word FROM coverage_analysis")
    #     cursor.execute("INSERT INTO title_normalized (word) SELECT DISTINCT word FROM coverage_analysis")
    #     cursor.execute("INSERT INTO title_tf_idf (word) SELECT DISTINCT word FROM coverage_analysis")

    #     conn.commit()

    # def retrieve_chunk_and_title_in_batch(batch_size: int):
    #     offset = 0
    #     while True:
    #         cursor.execute("SELECT file_name, chunk_text FROM pdf_chunks LIMIT ? OFFSET ?", (batch_size, offset))
    #         raw_data = cursor.fetchall()
    #         if not raw_data:
    #             break
    #         yield raw_data
    #         offset += batch_size

    # def normalize_vector(title_ids: list[str]) -> None:
    #     for title in title_ids:
    #         length = cursor.execute(f"SELECT SUM(title_{title} * title_{title}) FROM title_analysis").fetchone()[0]
    #         length = sqrt(length)
    #         cursor.execute(f"""
    #             UPDATE title_normalized
    #             SET title_{title} = 
    #                 (SELECT title_{title} FROM title_analysis WHERE title_normalized.word = title_analysis.word) / ?
    #         """, (1 + length,))
    #     conn.commit()

    # def compute_TF_IDF(title_ids: list[str]) -> None:
    #     DOCUMENT_COUNT = len(title_ids)
    #     for title in title_ids:
    #         total_terms = cursor.execute(f"SELECT SUM(title_{title}) FROM title_analysis").fetchone()[0]
    #         if total_terms == 0:
    #             continue  # Skip if no terms are found
            
    #         term_counts = cursor.execute(f"SELECT word, title_{title} FROM title_analysis").fetchall()
            
    #         for word, term_count in term_counts:
    #             if term_count == 0:
    #                 continue
                
    #             tf = term_count / total_terms
    #             doc_term = cursor.execute(f"""
    #                 SELECT * 
    #                 FROM title_analysis 
    #                 WHERE word = ?
    #             """, (word,)).fetchall()[0]
    #             doc_with_term = len([count for count in doc_term[1:] if count > 0])
                
    #             idf = log(DOCUMENT_COUNT / (1 + doc_with_term))
    #             cursor.execute(f"""
    #                 UPDATE title_tf_idf 
    #                 SET title_{title} = ? 
    #                 WHERE word = ?
    #             """, (tf * idf, word))
    #         conn.commit()

    # # Main flow
    # cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0")
    # titles = cursor.fetchall()
    # title_ids = [title[0] for title in titles]
    # print_and_log(f"Found {len(title_ids)} titles.")

    # cursor.execute("SELECT word FROM coverage_analysis")
    # words = {word[0]: 0 for word in cursor.fetchall()}
    # print_and_log(f"Found {len(words)} words.")

    # print_and_log("Creating tables...")
    # create_tables(title_ids=title_ids)

    # print_and_log("Retrieving and processing chunks...")
    # buffer = None
    # BATCH_SIZE = 100
    
    # for raw_data in retrieve_chunk_and_title_in_batch(batch_size=BATCH_SIZE):
    #     for file_name, chunk_text in raw_data:
    #         if not file_name.endswith(".pdf"):
    #             continue

    #         if buffer is None or file_name != buffer:
    #             if buffer:
    #                 log_message(f"Processing {buffer}")
    #                 ID_title = cursor.execute("SELECT id FROM file_list WHERE file_name = ?", (buffer.removesuffix('.pdf'),)).fetchone()[0]
    #                 cursor.executemany(
    #                     f"UPDATE title_analysis SET 'title_{ID_title}' = ? WHERE word = ?",
    #                     [(words[word], word) for word in words]
    #                 )
    #                 conn.commit()
    #                 log_message(f"Processed {buffer}")

    #             words = {word: 0 for word in words}  # Reset word counts
    #             buffer = file_name

    #         filtered_list = clean_text(chunk_text)
    #         for word in filtered_list:
    #             if word in words:
    #                 words[word] += 1

    # # Final processing for the last buffer
    # if buffer:
    #     log_message("Processing last buffer")
    #     ID_title = cursor.execute("SELECT id FROM file_list WHERE file_name = ?", (buffer.removesuffix('.pdf'),)).fetchone()[0]
    #     cursor.executemany(
    #         f"UPDATE title_analysis SET 'title_{ID_title}' = ? WHERE word = ?",
    #         [(words[word], word) for word in words]
    #     )
    #     conn.commit()
    #     log_message(f"Processed {buffer}")
    
    # # Normalizing vectors
    # print_and_log("Normalizing vectors...")
    # normalize_vector(title_ids=title_ids)
    # print_and_log("Finished normalizing vectors.")

    # # Compute TF-IDF
    # print_and_log("Computing TF-IDF...")
    # compute_TF_IDF(title_ids=title_ids)
    # print_and_log("Finished computing TF-IDF.")

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
            cursor.execute(f"SELECT title_{title} FROM title_normalized WHERE word = ?", (key,))
            title_list[title] += cursor.fetchone()[0] * normalized_prompt[key]

    top_10 = sorted(title_list.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Look up the name of the top 10 titles
    for title, score in top_10:
        cursor.execute("SELECT file_name FROM file_list WHERE id = ?", (title,))
        print(f"{score:.18f}: {title} - {cursor.fetchone()[0]}")

    conn.close()