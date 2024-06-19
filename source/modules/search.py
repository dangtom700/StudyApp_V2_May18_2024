import sqlite3
import colorama

from datetime import datetime
import modules.path as path
from modules.updateLog import log_message
from modules.extract_note import create_type_index_table

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

def setupTableReadingTask() -> None:
    database_name = path.chunk_database_path
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS reading_task ("
        "filename TEXT PRIMARY KEY, "
        "count INTEGER DEFAULT 0, "
        "Finished INTEGER DEFAULT 0, "
        "Unfished INTEGER DEFAULT 0)"
    )
    conn.commit()
    conn.close()

def getFilenameFromAnotherTable() -> list[str]:
    database_name = path.chunk_database_path
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute("SELECT pdf_name FROM pdf_list")
    filenames = cursor.fetchall()
    conn.close()
    return [filename[0] for filename in filenames]

def processDataFromTaskListFile() -> None:
    database_name = path.chunk_database_path
    setupTableReadingTask()

    filenames = getFilenameFromAnotherTable()
    # Initialize a dictionary to store filename as key and a list of [finished, unfinished] as value
    data = {filename: [0, 0] for filename in filenames}

    with open(path.taskList_path, 'r') as taskList_file:
        raw_text = taskList_file.readlines()[2:]
        for line in raw_text:
            if line == '\n':
                continue
            # if there are 2 commas in a line, skip this line
            if line.count(',') == 2:
                continue
            line = line.strip()
            filename = line.split('|')[1].removesuffix(']]')
            if filename not in data:
                data[filename] = [0, 0]  # Initialize if not already in data
            if line.startswith('- [x] '):
                data[filename][0] += 1
            elif line.startswith('- [ ] '):
                data[filename][1] += 1
    
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    for filename, counts in data.items():
        count = counts[0] + counts[1]
        cursor.execute(
            "INSERT OR REPLACE INTO reading_task (filename, count, Finished, Unfished) "
            "VALUES (?, ?, ?, ?)",
            (filename, count, counts[0], counts[1])
        )

    conn.commit()
    conn.close()

def randomizeNumberOfFilenameWithLowestCount() -> list[str]:
    database_name = path.chunk_database_path
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()

    # Select the minimum count value
    cursor.execute("SELECT MIN(count) FROM reading_task")
    min_count = cursor.fetchone()[0]

    # Select all filenames with the minimum count, then randomly limit to 3
    cursor.execute("""
        SELECT filename FROM reading_task
        WHERE count = ?
        ORDER BY RANDOM()
        LIMIT 3
    """, (min_count,))

    filenames = cursor.fetchall()
    conn.close()
    
    return filenames


def getTaskListFromDatabase() -> None:
    result = randomizeNumberOfFilenameWithLowestCount()
    
    log_message(f"Exporting task list to 'Task List.md' in {path.taskList_path}...")
    with open(path.Obsidian_taskList_path, 'a', encoding='utf-8') as f:
        f.write(f"\n{datetime.now().strftime("%a, %b %d, %Y")}\n\n")
        
        for task in result:
            # get value from tuple task
            file = task[0]
            f.write(f"- [ ] Read a chapter of [[BOOKS/{file}.pdf|{file}]]\n")
    log_message(f"Finished exporting task list to 'Task List.md' in {path.taskList_path}.")

    mirrorFile_to_destination(path.Obsidian_taskList_path, path.taskList_path)