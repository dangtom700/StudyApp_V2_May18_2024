import os
import re
import sqlite3
import logging
from datetime import datetime
from multiprocessing import Pool, Manager, Queue, Event, Lock, Process
from queue import Empty
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.layout import LAParams, LTTextBox, LTTextLine
from pdfminer.converter import PDFPageAggregator
from pdfminer.pdfpage import PDFTextExtractionNotAllowed

# --- Logging setup (File only, suppress noisy logs) ---
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"extract_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', handlers=[logging.FileHandler(log_file)])
logger = logging.getLogger(__name__)
for noisy in ["pdfminer", "pdfminer.layout", "pdfminer.converter", "pdfminer.pdfinterp"]:
    logging.getLogger(noisy).setLevel(logging.WARNING)

def clean_text(text):
    return re.sub(r'\s+', ' ', re.sub(r'\W+', ' ', text)).strip()

def text_to_chunks(text, chunk_size=512):
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
        """
        # TODO: Add error file to elimate the files to extract in the next run
        # 
        # with open("data\\error_files.txt", "a") as f:
        #     f.write(f"{file_name}\n")
        """

def db_writer(queue: Queue, event: Event, db_path: str, batch_size=1000):
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

    # Final flush
    if buffer:
        cursor.executemany(
            "INSERT OR IGNORE INTO pdf_text (file_name, chunk_id, chunk_text) VALUES (?, ?, ?)",
            buffer
        )
        conn.commit()
        logger.info(f"Final flush: {len(buffer)} chunks to DB")
    conn.close()

def extract_text(pdf_folder, chunk_size=512, reset_table=False, db_path="pdf_text.db"):
    logger.info(f"Extracting from: {pdf_folder}")
    manager = Manager()
    queue = manager.Queue()
    stop_event = manager.Event()

    files = [f for f in os.listdir(pdf_folder) if f.lower().endswith(".pdf")]
    file_set = set(files)

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
        """
        # TODO: Extract data from error_files.txt 
        # to extract non extracted files and except non-extractable files
        # with open("data\\error_files.txt", "r") as f:
        #     error_files = set(f.read().splitlines())
        # new_files = file_set - existing_files - error_files
        """
        new_files = file_set - existing_files

    file_tuples = sorted([(os.path.join(pdf_folder, f), f) for f in new_files])
    logger.info(f"Found {len(new_files)} new PDFs")

    # Start DB writer process
    writer = Process(target=db_writer, args=(queue, stop_event, db_path))
    writer.start()

    # Start PDF processors
    with Pool() as pool:
        pool.starmap(extract_and_stream, [(file_info, queue, chunk_size) for file_info in file_tuples])

    stop_event.set()
    writer.join()

    logger.info("All done.")