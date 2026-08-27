import os

# Best practice: try to load variables from a .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# __file__ gets the location of THIS script (src/modules/path.py).
module_dir = os.path.dirname(os.path.abspath(__file__)) # src/modules
src_dir = os.path.dirname(module_dir) # src
StudyApp_root_path = os.path.dirname(src_dir) + "\\" # project root with trailing slash
data_folder = os.path.join(StudyApp_root_path, "data")

pdf_path    = os.getenv("READING_LIST_PATH", "D:\\READING LIST")
source_data = os.getenv("RAW_DATA_PATH",      os.path.join(data_folder, "raw_text"))
dest_data   = os.getenv("REFINED_DATA_PATH",  os.path.join(data_folder, "refined_text"))

chunk_database_path = os.path.join(data_folder, "pdf_text.db")
token_json_path = os.path.join(data_folder, "token_json")

log_file_path = os.path.join(data_folder, "process.log")
# Ledger of every PDF the --compressPDF stage has touched. It is what stops a file
# being compressed twice; deleting it makes the next run re-compress the library.
compression_log_path = os.path.join(data_folder, "compression_log.csv")
# Content fingerprints of the library, so --dedupePDF can spot a re-download whose
# copy on disk has already been compressed (bytes differ, text does not). The cache
# is keyed on file size + mtime and is safe to delete -- it just gets rebuilt.
dedupe_cache_path = os.path.join(data_folder, "dedupe_fingerprints.json")
dedupe_log_path = os.path.join(data_folder, "dedupe_log.csv")
buffer_json_path = os.path.join(data_folder, "buffer.json")
dataset_path = os.path.join(data_folder, "dataset.txt")

# Paths configuration
DB_DIR = os.path.join(os.getcwd(), "vector_db")

# Models configuration
OLLAMA_BASE_URL = "http://localhost:11434"
EMBEDDING_MODEL = "embeddinggemma:latest"
LLM_MODEL = "gemma4:e4b"