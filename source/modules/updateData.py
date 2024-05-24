# Importing librairies

# Create a super function to extract text from pdf files with multi-threading, input list:
# - list of pdf files
# - output to database
# - chunk size for extracting text
# - Reset database option

# Create a super function to extract note titles with multi-threading, input list:
# - list of note files
# - output to database
# - Reset database option
import modules.path as path
import os
import sqlite3

def getFileList(path: str, fileType: str) -> list[str]:
    return [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and f.endswith(fileType)]

def processPDFfilesIntoDB(PDFlist: list[str], db_name: str, chunk_size: int, resetDB: bool) -> None:
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
        conn.commit()
        conn.close()

def processNoteFilesIntoDB(noteList: list[str], db_name: str, resetDB: bool) -> None:
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
            conn.commit()
            conn.close()

def updateData():
    PDFlist = getFileList(path.PDFpath, ".pdf")
    db_name = path.DB_name
    chunk_size = 1000
    resetDB = True
    processPDFfilesIntoDB(PDFlist, db_name, chunk_size, resetDB)
    noteList = getFileList(path.notePath, ".md")
    processNoteFilesIntoDB(noteList, db_name, resetDB)