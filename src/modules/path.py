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

pdf_path = os.getenv("READING_LIST_PATH", "D:\\READING LIST")
source_data = os.getenv("RAW_DATA_PATH", "D:\\reading_raw_dataset")
dest_data = os.getenv("REFINED_DATA_PATH", "D:\\reading_refined_dataset")

chunk_database_path = os.path.join(data_folder, "pdf_text.db")
token_json_path = os.path.join(data_folder, "token_json")

log_file_path = os.path.join(data_folder, "process.log")
buffer_json_path = os.path.join(data_folder, "buffer.json")
dataset_path = os.path.join(data_folder, "dataset.txt")

# Paths configuration
DB_DIR = r"./vector_db"

# Models configuration
OLLAMA_BASE_URL = "http://localhost:11434"
EMBEDDING_MODEL = "embeddinggemma:latest"
LLM_MODEL = "gemma:e4b"