import os
import re
import sqlite3
import logging
import signal
import sys
from datetime import datetime
from multiprocessing import Pool, Manager, Queue, Event, Process
from queue import Empty
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.layout import LAParams, LTTextBox, LTTextLine
from pdfminer.converter import PDFPageAggregator
from pdfminer.pdfpage import PDFTextExtractionNotAllowed

# --- Constants ---
CHUNK_SIZE_DEFAULT = 512
DB_NAME_DEFAULT = "pdf_text.db"
BATCH_SIZE_DB = 1000
LOG_DIR = "logs"
ERROR_FILE = "data\\error_files.txt"

# --- Logging Setup ---
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, f"extract_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(log_file)]
)
logger = logging.getLogger(__name__)
for noisy in ["pdfminer", "pdfminer.layout", "pdfminer.converter", "pdfminer.pdfinterp"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

# --- Utility Functions ---
def clean_text(text):
    return re.sub(r'\s+', ' ', re.sub(r'\W+', ' ', text)).strip()

def text_to_chunks(text, chunk_size):
    words = text.split()
    return [' '.join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]

def pdf_to_text(pdf_path, password=""):
    text = ""
    with open(pdf_path, "rb") as fp:
        parser = PDFParser(fp)
        doc = PDFDocument(parser, password)
        if not doc.is_extractable:
            raise PDFTextExtractionNotAllowed
        device = PDFPageAggregator(PDFResourceManager(), laparams=LAParams())
        interpreter = PDFPageInterpreter(PDFResourceManager(), device)
        for page in PDFPage.create_pages(doc):
            interpreter.process_page(page)
            layout = device.get_result()
            for obj in layout:
                if isinstance(obj, (LTTextBox, LTTextLine)):
                    text += obj.get_text()
    return clean_text(text)

# --- Worker & DB Writer ---
def extract_and_stream(file_info, queue: Queue, chunk_size):
    file_path, file_name = file_info
    try:
        text = pdf_to_text(file_path)
        chunks = text_to_chunks(text, chunk_size)
        for idx, chunk in enumerate(chunks):
            queue.put((file_name, idx, chunk))
        logger.info(f"[{file_name}] Extracted {len(chunks)} chunks")
    except Exception as e:
        logger.error(f"[{file_name}] Extraction failed: {e}")
        with open(ERROR_FILE, "a") as f:
            f.write(f"{file_name}\n")

def db_writer(queue: Queue, event, db_path: str, batch_size=BATCH_SIZE_DB):
    buffer = []
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    while not event.is_set() or not queue.empty():
        try:
            item = queue.get(timeout=1)
            buffer.append(item)
            if len(buffer) >= batch_size:
                cursor.executemany(
                    "INSERT OR IGNORE INTO pdf_text (file_name, chunk_id, chunk_text) VALUES (?, ?, ?)",
                    buffer
                )
                conn.commit()
                logger.info(f"Flushed {len(buffer)} chunks to DB")
                buffer.clear()
        except Empty:
            continue
    if buffer:
        cursor.executemany(
            "INSERT OR IGNORE INTO pdf_text (file_name, chunk_id, chunk_text) VALUES (?, ?, ?)",
            buffer
        )
        conn.commit()
        logger.info(f"Final flush: {len(buffer)} chunks to DB")
    conn.close()

# --- Main Extraction Function ---
def extract_text(pdf_folder, chunk_size=CHUNK_SIZE_DEFAULT, reset_table=False, db_path=DB_NAME_DEFAULT, num_workers=None):
    logger.info(f"Extracting from: {pdf_folder}")
    manager = Manager()
    queue = manager.Queue()
    stop_event = manager.Event()

    # Setup graceful shutdown
    def graceful_shutdown(signum, frame):
        logger.warning("Received shutdown signal, stopping processes...")
        stop_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    file_set = set(files)

    error_files = set()
    if os.path.exists(ERROR_FILE):
        with open(ERROR_FILE, "r") as f:
            error_files = set(f.read().splitlines())

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if reset_table:
            cursor.execute("DROP TABLE IF EXISTS pdf_text")
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

    new_files = file_set - existing_files - error_files
    logger.info(f"Found {len(new_files)} new PDFs")

    file_tuples = sorted([(os.path.join(pdf_folder, f), f) for f in new_files])

    writer = Process(target=db_writer, args=(queue, stop_event, db_path))
    writer.start()

    with Pool(processes=num_workers) as pool:
        pool.starmap(extract_and_stream, [(file_info, queue, chunk_size) for file_info in file_tuples])

    stop_event.set()
    writer.join()

    logger.info(f"Processed {len(new_files)} PDFs")
    logger.info(f"Skipped {len(existing_files)} already in DB")
    logger.info(f"Errored: {len(error_files)} previously known failures")
    logger.info("All done.")
