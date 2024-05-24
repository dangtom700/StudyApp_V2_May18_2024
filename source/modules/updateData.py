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
    pass

def processNoteFilesIntoDB(noteList: list[str], db_name: str, resetDB: bool) -> None:
    pass

def updateData():
    PDFlist = getFileList(path.PDFpath, ".pdf")
    db_name = path.DB_name
    chunk_size = 1000
    resetDB = True
    processPDFfilesIntoDB(PDFlist, db_name, chunk_size, resetDB)
    noteList = getFileList(path.notePath, ".md")
    processNoteFilesIntoDB(noteList, db_name, resetDB)