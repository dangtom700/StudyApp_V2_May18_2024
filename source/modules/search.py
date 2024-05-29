import sqlite3
import colorama

from datetime import datetime
from modules.path import taskList_path, Obsidian_taskList_path
from modules.updateLog import log_message

def mirrorFile_to_destination(source: str, destination: str) -> None:
    with open(source, 'r', encoding='utf-8') as read_obj, open(destination, 'w', encoding='utf-8') as write_obj:
        for line in read_obj:
            write_obj.write(line)

def searchFileInDatabase(keyword: str) -> None:
    try:
        conn = sqlite3.connect('data\\chunks.db')
        cursor = conn.cursor()

        type_search = ["note", "pdf"]

        for type in type_search:
            cursor.execute(f"SELECT {type}_name FROM {type}_list WHERE {type}_name LIKE ?", (f'%{keyword}%',))
            result = cursor.fetchall()

            print(f"{colorama.Fore.GREEN}{type.capitalize()} files containing '{keyword}':{colorama.Style.RESET_ALL}\n")
            for file_name in result:
                print(f"- {colorama.Fore.BLUE}{file_name[0]}{colorama.Style.RESET_ALL}\n")

    except sqlite3.Error as e:
        print(f"Error searching files in database: {e}")
    finally:
        if conn:
            conn.close()

def getTaskListFromDatabase() -> None:
    try:
        conn = sqlite3.connect('data\\chunks.db')
        cursor = conn.cursor()
        cursor.execute("SELECT pdf_name FROM pdf_list ORDER BY RANDOM() LIMIT 3")
        result = cursor.fetchall()

        log_message(f"Exporting task list to 'Task List.md' in {taskList_path}...")
        with open(Obsidian_taskList_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{datetime.now().strftime("%a, %b %d, %Y")}\n\n")
            
            for task in result:
                # get value from tuple task
                file = task[0]
                f.write(f"- [ ] Read a chapter of [[BOOKS/{file}.pdf|{file}]]\n")
        log_message(f"Finished exporting task list to 'Task List.md' in {taskList_path}.")

        mirrorFile_to_destination(Obsidian_taskList_path, taskList_path)

    except sqlite3.Error as e:
        print(f"Error exporting task list: {e}")
    finally:
        if conn:
            conn.close()