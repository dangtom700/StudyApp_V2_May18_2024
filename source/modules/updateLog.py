import sqlite3
import time
from modules.path import log_database_path, chunk_database_path, pdf_path
from os import listdir, makedirs
from os.path import isdir, basename, join, exists
import shutil

def getCurrentTime() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
def log_message(message: str) -> None:
    database_name = log_database_path
    current_time = getCurrentTime()
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO messages (timestamp, message_type, message) VALUES (?, ?, ?)", (current_time,"PROGRESS",message))
    conn.commit()
    conn.close()

def store_log_file_to_database(log_file_path: str) -> None:
    database_name = log_database_path
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS messages (timestamp TEXT, message_type TEXT, message TEXT)")
    with open(log_file_path, 'r') as log_file:
        for line in log_file:
            timestamp, message_type, message = line.strip().split(' - ')
            cursor.execute("INSERT INTO messages (timestamp, message_type, message) VALUES (?, ?, ?)", (timestamp, message_type, message))

    cursor.execute("INSERT INTO messages (timestamp, message_type, message) VALUES (?, ?, ?)", (getCurrentTime(), "PROGRESS", "FINISHED UPDATING LOG FILE"))
    conn.commit()
    conn.close()
    # empty_log_file
    with open(log_file_path, 'w') as log_file:
        pass
def create_cs_file(source_path: str, extension: str) -> None:

    if not isdir(source_path):
        return None

    path = {".md": "data/note_list.md", 
            ".pdf": "data/pdf_list.md"}
    with open(path[extension], 'w') as f:
        for file in listdir(source_path):
            if file.endswith(extension):
                f.write(basename(file).removesuffix(extension) + ', ')

def categorize_pdf_files_by_theme(source_path: str) -> None:
    categories = {
    "Computer Science and Engineering": ["Algorithms and Data Structures", "Programming Languages and Software Development", "Database Systems and Management", "Computer Architecture and Organization", "Computer Networks and Security", "Artificial Intelligence and Machine Learning", "Robotics and Automation", "Computer Graphics and Visualization", "Embedded Systems and IoT"],
    "Mathematics and Statistics": ["Statistics and Probability", "Mathematical Modeling and Optimization", "Numerical Methods", "Discrete Mathematics", "Game Theory"],
    "Business and Economics": ["Economics and Econometrics", "Finance and Accounting", "Management and Organizational Behavior", "Marketing and Business Analytics", "Operations Research and Supply Chain"],
    "Engineering (General)": ["Engineering Mechanics and Materials", "Thermodynamics and Fluid Mechanics", "Electrical Engineering", "Control Systems and Automation", "Signal Processing and Communication", "Energy and Environment"],
    "Science and Technology": ["Physics", "Chemistry", "Biology", "Nanotechnology", "Materials Science", "Agriculture and Food Science"],
    "Social Sciences":["Philosophy and Ethics", "History and Social Sciences", "Design and Human-Computer Interaction"]
    }

def categorize_pdf_files_by_month_year(destination_path = "D:\\ReadingMaterial") -> None:
    def convert_date(date: str) -> str:
        # Sun, Apr 14, 2024, 22:21:05 to create 2024-04 as a folder to sort files
        date = date.split(", ")
        year = date[2]
        month = date[1][:3]
        return f"{year}-{month}"
    def filter_date(raw_data: dict) -> dict:
        # organize by month and year
        date_to_pdf = {}
        for pdf_name in raw_data.keys():
            date = convert_date(raw_data[pdf_name])
            if date not in date_to_pdf:
                date_to_pdf[date] = []
            date_to_pdf[date].append(pdf_name)

        return date_to_pdf
    conn = sqlite3.connect(chunk_database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT pdf_path, created_time FROM pdf_list")
    rows = cursor.fetchall()
    rows = {row[0]: row[1] for row in rows}
    conn.close()
    
    print(len(rows))
    counter = 0

    filtered_data = filter_date(rows)

    # copy files from the original folder to the destination folder
    for date in filtered_data.keys():
        pdf_list = filtered_data[date]
        if not exists(join(destination_path, date)):
            makedirs(join(destination_path, date))
        
        destination_file = join(destination_path, date)
        
        for pdf_path in pdf_list:
            if exists(join(destination_path, date, basename(pdf_path))):
                continue
            # destination_file = join(destination_path, date, basename(pdf_path))
            shutil.copy2(pdf_path, destination_file)

            counter += 1
            print(counter)
            print(pdf_path)