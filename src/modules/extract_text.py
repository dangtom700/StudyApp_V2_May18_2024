import os
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
# from multiprocessing import Pool, Value, Lock
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.layout import LAParams, LTTextBox, LTTextLine
from pdfminer.converter import PDFPageAggregator
from pdfminer.pdfpage import PDFTextExtractionNotAllowed

import logging
from datetime import datetime

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, f"extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.getLogger("pdfminer").setLevel(logging.WARNING)

# --- Config ---
ERROR_FILE = "data\\error_files.txt"
CHUNK_TANK_THRESHOLD = 1000
CHUNK_SIZE_DEFAULT = 512
MAX_THREADS = 20
# MAX_PROCESSORS = 8
SAMPLE_PATH = "dataset"
DB_NAME_DEFAULT = "pdf_text.db"
PAGE_LIMIT = 3

# --- Helpers ---
def clean_text(text):
    return re.sub(r'\s+', ' ', re.sub(r'\W+', ' ', text)).strip()

def text_to_chunks(text, chunk_size):
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def pdf_to_text(pdf_path, chunk_size=CHUNK_SIZE_DEFAULT, password=""):
    logging.info(f"PROCESSING: {os.path.basename(pdf_path)}")
    page_count = 0
    text = ""
    write_path = os.path.join(SAMPLE_PATH, os.path.basename(pdf_path).replace(".pdf", ".txt"))
    os.makedirs(SAMPLE_PATH, exist_ok=True)

    try:
        with open(pdf_path, "rb") as fp:
            parser = PDFParser(fp)
            doc = PDFDocument(parser, password)
            if not doc.is_extractable:
                raise PDFTextExtractionNotAllowed

            rsrcmgr = PDFResourceManager()
            device = PDFPageAggregator(rsrcmgr, laparams=LAParams())
            interpreter = PDFPageInterpreter(rsrcmgr, device)

            for page in PDFPage.create_pages(doc):
                page_count += 1
                interpreter.process_page(page)
                layout = device.get_result()

                for obj in layout:
                    if isinstance(obj, (LTTextBox, LTTextLine)):
                        text += obj.get_text()

                # Every PAGE_LIMIT pages, flush processed text to file
                if page_count % PAGE_LIMIT == 0:
                    page_count = 0 # Reset
                    buffer_text = clean_text(text)
                    chunks = text_to_chunks(buffer_text, chunk_size)

                    # Hold onto final partial chunk
                    if chunks and len(chunks[-1].split()) < chunk_size:
                        text = chunks.pop()  # Keep last partial for next round
                    else:
                        text = ""

                    with open(write_path, "a", encoding="utf-8") as f:
                        for chunk in chunks:
                            f.write(chunk + "\n")

            # Final flush after last page
            if text.strip():
                buffer_text = clean_text(text)
                chunks = text_to_chunks(buffer_text, chunk_size)
                with open(write_path, "a", encoding="utf-8") as f:
                    for chunk in chunks:
                        f.write(chunk + "\n")

        logging.info(f"[SUCCESS] {os.path.basename(pdf_path)}")

    except Exception as e:
        logging.error(f"[ERROR] {os.path.basename(pdf_path)}: {e}")
        os.makedirs(os.path.dirname(ERROR_FILE), exist_ok=True)
        with open(ERROR_FILE, "a") as f:
            f.write(os.path.basename(pdf_path) + "\n")

# --- Main ---
def extract_text(pdf_folder, chunk_size=CHUNK_SIZE_DEFAULT, db_path=DB_NAME_DEFAULT):
    logging.info(f"Starting extraction in: {pdf_folder}")
    if not os.path.exists(pdf_folder):
        logging.error(f"Folder does not exist: {pdf_folder}")
        return

    # Prep DB
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_text (
            file_name TEXT,
            chunk_id INTEGER,
            chunk_text TEXT,
            PRIMARY KEY (file_name, chunk_id)
        )
    """)
    cursor.execute("SELECT DISTINCT file_name FROM pdf_text")
    existing_files = set(row[0] for row in cursor.fetchall())

    # Prep list
    error_files = set()
    if os.path.exists(ERROR_FILE):
        with open(ERROR_FILE, "r") as f:
            error_files = set(f.read().splitlines())

    all_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]

    if os.path.exists(SAMPLE_PATH):
        files_in_text_chunk_folder = set([f.replace(".txt", ".pdf") for f in os.listdir(SAMPLE_PATH) if f.lower().endswith(".txt")])
    else:
        files_in_text_chunk_folder = set()
    
    new_files = set(all_files) - existing_files - error_files - files_in_text_chunk_folder
    # Order by file size, ascending
    new_files = sorted(new_files, key=lambda f: os.path.getsize(os.path.join(pdf_folder, f)))
    logging.info(f"Found {len(new_files)} new PDFs")

    # Create a text folder if it doesn't exist
    os.makedirs(SAMPLE_PATH, exist_ok=True)

    # --- Step 1: Extract text with threads ---
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = []
        for file in new_files:
            pdf_path = os.path.join(pdf_folder, file)
            futures.append(executor.submit(pdf_to_text, pdf_path, chunk_size))

        for future in as_completed(futures):
            exception = future.exception()
            if exception:
               logging.error(f"[Thread Error] {exception}")

    # # --- Step 1: Extract text with Processors ---
    # with Pool(processes=MAX_PROCESSORS) as pool:
    #     pool.starmap_async(
    #         pdf_to_text,
    #         [(os.path.join(pdf_folder, file), chunk_size) for file in new_files]
    #     ).wait()

    # --- Step 2: Read chunks from .txt files ---
    chunks = []
    txt_files = [f for f in os.listdir(SAMPLE_PATH) if f.lower().endswith(".txt")]

    for file in txt_files:
        file_path = os.path.join(SAMPLE_PATH, file)
        with open(file_path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                chunks.append((file.replace(".txt", ".pdf"), idx, line.strip()))

        if len(chunks) >= CHUNK_TANK_THRESHOLD:
            cursor.executemany("INSERT OR IGNORE INTO pdf_text (file_name, chunk_id, chunk_text) VALUES (?, ?, ?)", chunks)
            conn.commit()
            logging.info(f"Inserted {len(chunks)} chunks to DB")
            chunks = []

    # Final insert
    if chunks:
        cursor.executemany("INSERT OR IGNORE INTO pdf_text (file_name, chunk_id, chunk_text) VALUES (?, ?, ?)", chunks)
        conn.commit()
        logging.info(f"Final insert of {len(chunks)} chunks")

    conn.close()
    logging.info("Extraction complete.")
