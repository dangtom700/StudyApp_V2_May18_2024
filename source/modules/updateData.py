import os
import sqlite3
import concurrent.futures
import time
import fitz  # PyMuPDF
import modules.path as path
from langchain import RecursiveCharacterTextSplitter

def getFileList(folder_path: str, fileType: str) -> list[str]:
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.endswith(fileType)]

def processPDFfilesIntoDB(folder_path: str, db_name: str, chunk_size: int, resetDB: bool) -> None:
    def setup_database(db_name, reset_db):
        """
        Set up the database for storing PDF chunks and word frequencies.
        
        Args:
            db_name (str): The name of the database file.
            reset_db (bool): Whether to reset the database by dropping existing tables.
        
        Returns:
            None
        """
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        if reset_db:
            cursor.execute('DROP TABLE IF EXISTS pdf_chunks')
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

    def log_message(db_name, message):
        """
        Log messages into the database.
        
        Args:
            db_name (str): The name of the database file.
            message (str): The log message.
        
        Returns:
            None
        """
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO log (timestamp, message) VALUES (datetime('now'), ?)
        ''', (message,))
        conn.commit()
        conn.close()

    def extract_text_from_pdf(pdf_file):
        """
        Extract text from a PDF file.
        
        Args:
            pdf_file (str): The path to the PDF file.
        
        Returns:
            str: The extracted text.
        """
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
    
    def split_text_into_chunks(text, chunk_size):
        """
        Split text into chunks.
        
        Args:
            text (str): The text to split.
            chunk_size (int): The size of each chunk.
        
        Returns:
            list[str]: A list of text chunks.
        """
        log_message(db_name, f"Splitting text into chunks of {chunk_size} characters...")
        if not isinstance(text, str):
            log_message(db_name, f"Expected text to be a string but got {type(text)}.")
            return []
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=0)
        try:
            chunks = text_splitter.split_text(text)
        except Exception as e:
            log_message(db_name, f"Error splitting text: {e}")
            chunks = []
        log_message(db_name, f"Finished splitting text into chunks.")
        return chunks
    
    def store_chunks_in_db(file_name, chunks, db_name):
        """
        Store text chunks in the database with a retry mechanism.
        
        Args:
            file_name (str): The name of the file.
            chunks (list[str]): The text chunks.
            db_name (str): The name of the database.
        
        Returns:
            None
        """
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
                log_message(db_name, f"Attempt {attempt + 1} to store {file_name} failed with error: {e}. Retrying...")
                attempt += 1
                time.sleep(5)  # Sleep for a short time before retrying
            finally:
                conn.close()
        if not success:
            log_message(db_name, f"Failed to insert chunks for {file_name} after {attempt} attempts.")
        else:
            log_message(db_name, f"Stored {len(chunks)} chunks for {file_name} in the database.")
    
    def process_file(pdf_file):
        """
        Process a single PDF file: extract text, split into chunks, and store in database.
        
        Args:
            pdf_file (str): The path to the PDF file.
        
        Returns:
            None
        """
        text = extract_text_from_pdf(pdf_file)
        if text:
            chunks = split_text_into_chunks(text, chunk_size)
            if chunks:
                store_chunks_in_db(pdf_file, chunks, db_name)
    
    # Main execution flow
    setup_database(db_name, resetDB)
    pdf_files = getFileList(folder_path, ".pdf")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(process_file, pdf_files)

def processNoteFilesIntoDB(note_folder_path: str, db_name: str, resetDB: bool) -> None:
    def setup_database(db_name, reset_db):
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        if reset_db:
            cursor.execute('DROP TABLE IF EXISTS note_file')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS note_file (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_name TEXT NOT NULL,
                    primary_key TEXT,
                    PDF_source TEXT
                )
            ''')
            cursor.execute('DROP TABLE IF EXISTS log')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    message TEXT
                )
            ''')
        conn.commit()
        conn.close()
        
    def log_message(db_name, message):
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO log (timestamp, message) VALUES (datetime('now'), ?)
        ''', (message,))
        conn.commit()
        conn.close()
    
    def extract_word_from_file_name(file_name: str) -> list:
        filename = os.path.basename(file_name).split(".")[0]
        primary_keys = filename.split(" ")
        return [key for key in primary_keys if len(key) > 3]
    
    def store_note_table_in_db(file_name, primary_keys, db_name):
        attempt = 0
        success = False
        while attempt < 999 and not success:
            try:
                conn = sqlite3.connect(db_name)
                cursor = conn.cursor()
                for index, chunk in enumerate(primary_keys):
                    cursor.execute('''
                        INSERT INTO note_file (note_name, primary_key, PDF_source) VALUES (?, ?, ?)
                    ''', (os.path.basename(file_name), chunk, None))
                conn.commit()
                success = True
            except sqlite3.Error as e:
                log_message(db_name, f"Attempt {attempt + 1} failed with error: {e}. Retrying...")
                attempt += 1
                time.sleep(5)  # Sleep for a short time before retrying
            finally:
                conn.close()
        if not success:
            log_message(db_name, f"Failed to insert {file_name} after {attempt} attempts.")
        else:
            log_message(db_name, f"Successfully inserted {file_name}.")

    def process_file(file_name):
        primary_keys = extract_word_from_file_name(file_name)
        store_note_table_in_db(file_name, primary_keys, db_name)
    
    # Main execution flow
    setup_database(db_name, resetDB)
    note_file_list = getFileList(note_folder_path, ".md")
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(process_file, note_file_list)

def updateData():
    db_name = path.DB_name
    chunk_size = 1000
    resetDB = True
    processPDFfilesIntoDB(path.BOOKS_folder_path, db_name, chunk_size, resetDB)
    processNoteFilesIntoDB(path.StudyNote_folder_path, db_name, resetDB)