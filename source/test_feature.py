""" Distributed random files for task list generation
# The table name reading_task consists of filename TEXT, count INTEGER default 0
# Copy the data column that consists of filename from a table to filename column
#  in reading_task table
# Read in the task list file and extract the filename and count its frequency
# Stucture of the task list file (sample):
'''
Thu, May 10, 2024

- [x] Read a chapter of [[internet afterlife virtual salvation in the 21st century.pdf|internet afterlife virtual salvation in the 21st century]]
- [x] Read a chapter of [[information science.pdf|information science]]
- [x] Read a chapter of [[media and development.pdf|media and development]]

'''
Note: Exclude the first two lines of the task list file (title and new line),
the format for the rest of the file is the same as the above example
"""
import sqlite3
from modules.path import chunk_database_path, taskList_path

def setupTableReadingTask() -> None:
    database_name = chunk_database_path
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
    database_name = chunk_database_path
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    cursor.execute("SELECT pdf_name FROM pdf_list")
    filenames = cursor.fetchall()
    conn.close()
    return [filename[0] for filename in filenames]

def processDataFromTaskListFile() -> None:
    database_name = chunk_database_path
    setupTableReadingTask()

    filenames = getFilenameFromAnotherTable()
    # Initialize a dictionary to store filename as key and a list of [finished, unfinished] as value
    data = {filename: [0, 0] for filename in filenames}

    with open(taskList_path, 'r') as taskList_file:
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
    database_name = chunk_database_path
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

processDataFromTaskListFile()
print(randomizeNumberOfFilenameWithLowestCount())