import sqlite3
import colorama
from modules.path import taskList_path, Obsidian_taskList_path, database_path
from modules.updateData import log_message

# Function to securely copy contents of source file to destination file
def mirrorFile_to_destination(source: str, destination: str) -> None:
    with open(source, 'r', encoding='utf-8') as read_obj, open(destination, 'w', encoding='utf-8') as write_obj:
        for line in read_obj:
            write_obj.write(line)

# Function to export task list
def getTaskList() -> None:
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT file_name FROM pdf_index ORDER BY RANDOM() LIMIT 3")
        result = cursor.fetchall()
        
        log_message(database_path, f"Exporting task list to 'Task List.md' in {taskList_path}...")
        with open(taskList_path, 'w', encoding='utf-8') as f:
            for file_name in result:
                f.write(f"- [ ] Read a chapter in {file_name[0]}\n")
        log_message(database_path, f"Finished exporting task list to 'Task List.md' in {taskList_path}.")
        
        mirrorFile_to_destination(taskList_path, Obsidian_taskList_path)
        
    except sqlite3.Error as e:
        print(f"Error exporting task list: {e}")
    finally:
        if conn:
            conn.close()

# Function to search files in database
def searchFileInDatabase(keyword: str) -> None:
    try:
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()

        # Search PDF files
        cursor.execute("SELECT file_name FROM pdf_index WHERE file_name LIKE ?", (f'%{keyword}%',))
        pdf_result = cursor.fetchall()

        # Search notes
        cursor.execute("SELECT note_name FROM note_list WHERE file_name LIKE ?", (f'%{keyword}%',))
        result = cursor.fetchall()

        print(f"{colorama.Fore.BLUE}PDF files containing '{keyword}':{colorama.Style.RESET_ALL}\n")
        for file_name in pdf_result:
            print(f"- {colorama.Fore.BLUE}{file_name[0]}{colorama.Style.RESET_ALL}\n")

        print(f"{colorama.Fore.BLUE}Notes containing '{keyword}':{colorama.Style.RESET_ALL}\n")
        for note_name in result:
            print(f"- {colorama.Fore.BLUE}{note_name[0]}{colorama.Style.RESET_ALL}\n")

    except sqlite3.Error as e:
        print(f"Error searching files in database: {e}")
    finally:
        if conn:
            conn.close()
