from os import getcwd

StudyApp_root_path = getcwd() + "\\"

pdf_path = "D:\\READING LIST"
source_data = "D:\\reading_raw_dataset"
dest_data = "D:\\reading_refined_dataset"

chunk_database_path = StudyApp_root_path + "data\\pdf_text.db"
token_json_path = StudyApp_root_path + "data\\token_json"

log_file_path = StudyApp_root_path + "data\\process.log"
buffer_json_path = StudyApp_root_path + "data\\buffer.json"
dataset_path = StudyApp_root_path + "data\\dataset.txt"