""" command to export data from database to file
--exportTagSet
--exportPDF_info
--exportPDF_index
--updateStat
--exportPDF_token
--updateData
--getTaskList
--searchFile
"""
import modules.path as path
import sqlite3
import colorama

def exportTagSet() -> None:
    pass
def exportPDFindex() -> None:
    pass
def getTaskList() -> None:
    pass
    
def searchFileInDatabase(keyword: str) -> None:
    conn = sqlite3.connect(path.db_name)
    cursor = conn.cursor()
    cursor.execute(f"SELECT file_name FROM pdf_index WHERE file_name LIKE '%{keyword}%'")
    result = cursor.fetchall()
    conn.close()
    
    colorama.init(autoreset=True)
    print(f"{colorama.Fore.BLUE}Result:{colorama.Style.RESET_ALL}\n")
    for file_name in result:
        print(f"- {colorama.Fore.BLUE}{file_name}{colorama.Style.RESET_ALL}\n")
