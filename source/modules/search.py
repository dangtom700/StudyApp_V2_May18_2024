import sqlite3
import colorama
import datetime
import modules.path as path
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
            # print(f"files containing '{keyword}':\n")
            for file_name in result:
                print(f"- {colorama.Fore.BLUE}{file_name[0]}{colorama.Style.RESET_ALL}\n")
                # print(f"- {file_name[0]}\n")

    except sqlite3.Error as e:
        print(f"Error searching files in database: {e}")
    finally:
        if conn:
            conn.close()

def setupTableReadingTask(reset_db: bool = True) -> None:
    database_name = path.chunk_database_path
    conn = sqlite3.connect(database_name)
    cursor = conn.cursor()
    
    if reset_db:
        cursor.execute("DROP TABLE IF EXISTS reading_task")
    
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
            if "|" not in line:
                continue
            line = line.strip()
            filename = line.split('|')[1]
            filename = filename.removesuffix(']]')

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

def getTaskListFromDatabase(date_now = datetime.datetime.now()) -> None:
    result = randomizeNumberOfFilenameWithLowestCount()
    conn = sqlite3.connect(path.chunk_database_path)

    cursor = conn.cursor()
    # increare by 1 in count column for every filename in result
    for filename in result:
        cursor.execute("UPDATE reading_task SET count = count + 1 WHERE filename = ?", (filename[0],))
    conn.commit()
    conn.close()
    log_message("Finished updating count in database.")
    
    log_message(f"Exporting task list to 'Task List.md' in {path.taskList_path}...")
    with open(path.Obsidian_taskList_path, 'a', encoding='utf-8') as f:
        f.write(f"\n{date_now.strftime('%a, %b %d, %Y')}\n\n")
        
        for task in result:
            # get value from tuple task
            file = task[0]
            f.write(f"- [ ] Read a chapter of [[BOOKS/{file}.pdf|{file}]]\n")
    log_message(f"Finished exporting task list to 'Task List.md' in {path.taskList_path}.")
    print(f"Finished updating task list record.")

    mirrorFile_to_destination(path.Obsidian_taskList_path, path.taskList_path)

def randomizeNoteList():
    conn = sqlite3.connect(path.chunk_database_path)
    cursor = conn.cursor()
    cursor.execute("SELECT note_name FROM note_list ORDER BY RANDOM() LIMIT 3")
    result = cursor.fetchall()
    conn.close()
    result = [note[0] for note in result]
    log_message(f"Note list randomized: {result}")
    return result

def exportNoteReviewTask(note_list: list, date: str) -> None:
    with open (path.Obsidian_noteReview_path, 'a', encoding='utf-8') as f:
        f.write(f"\n[[{date}]]\n\n")
        for note in note_list:
            f.write(f"- {note}\n")
    log_message("Note review task exported.")
    mirrorFile_to_destination(path.Obsidian_noteReview_path, path.noteReview_path)

def exportStudyLogTemplate(note_list: list, date: str) -> None:
    note_list = [f"[[StudyNotes/{note}.md|{note}]]" for note in note_list]
    with open (path.Obsidian_template_path, 'rb') as f:
        # get al content from template
        content = f.read()

    with open (f"{path.Obsidian_review_folder_path}{date}.md", 'w', encoding='utf-8') as f:
        change_date = content.decode('utf-8').replace("Date: {date}", f"Date: {date}")
        change_note = change_date.replace("- {note1}\n- {note2}\n- {note3}", f"- {note_list[0]}\n- {note_list[1]}\n- {note_list[2]}")

        f.write(change_note)

    log_message("Modified study log template exported to 'Review' folder.")

def getNoteReviewTask() -> None:
    note_list = randomizeNoteList()
    date = datetime.datetime.now().strftime("%b_%d_%Y")
    exportNoteReviewTask(note_list, date)
    exportStudyLogTemplate(note_list, date)

def create_task_list_in_time_range(start_date: datetime.datetime, end_date: datetime.datetime) -> None:
    current_date = start_date
    while current_date <= end_date:
        log_message(f"Exporting task list to 'Task List.md' in {path.Obsidian_taskList_path}...")
        getTaskListFromDatabase(current_date)
        log_message(f"Finished exporting task list to 'Task List.md' in {path.Obsidian_taskList_path} for {current_date}.")
        current_date += datetime.timedelta(days=1)
    print(f"Finished updating task list record.")

def getWordFrequencyAnalysis(batch_size = 100, threshold = 0.82) -> int:
    conn = sqlite3.connect(path.chunk_database_path)
    cursor = conn.cursor()

    # Order the table in descending order
    cursor.execute("SELECT * FROM word_frequencies ORDER BY frequency DESC")

    # get the sum of frequency from the table
    cursor.execute("SELECT SUM(frequency) FROM word_frequencies")
    sum_frequency = cursor.fetchone()[0]
    print(f"Sum of frequency: {sum_frequency}")

    # get the average of frequency from the table
    cursor.execute("SELECT AVG(frequency) FROM word_frequencies")
    avg_frequency = cursor.fetchone()[0]
    print(f"Average of frequency: {avg_frequency}")

    print("Generating report...")
    with open(path.WordFrequencyAnalysis_path, 'w', encoding='utf-8') as f:
        # Default parameters
        counting_frequency = 0
        offset = 0
        # Write the header
        f.write("# Word frequency analysis\n\n")
        # Write the main report
        f.write("### Word frequency analysis:\n\n")
        f.write("|Iteration|Counting frequency|Coverage|Frequency gain|Coverage gain|Word count|\n")
        f.write("|---------|------------------|--------|--------------|-------------|----------|\n")
        
        coverage = counting_frequency / sum_frequency

        while coverage < threshold:
            cursor.execute("SELECT SUM(frequency) FROM (SELECT frequency FROM word_frequencies ORDER BY frequency DESC LIMIT ? OFFSET ?)", (batch_size, offset))
            batch_sum = cursor.fetchone()[0]
            
            if batch_sum is None:  # In case there are no more rows to fetch
                break
            
            counting_frequency += batch_sum
            offset += batch_size

            previous_coverage = coverage
            coverage = counting_frequency / sum_frequency
            coverage_gain = coverage - previous_coverage

            f.write(f"|{int(offset / batch_size)}")
            f.write(f"|{counting_frequency}")
            f.write(f"|{coverage:.2%}")
            f.write(f"|{batch_sum}")
            f.write(f"|{coverage_gain:.2%}")
            f.write(f"|{offset}|\n")

        f.write("\n\n")

        # Write the words with the best coverage
        cursor.execute("SELECT * FROM word_frequencies ORDER BY frequency DESC LIMIT ?", (offset,))

        f.write("### Words of best coverage:\n\n")
        f.write("|Word|Frequency|Word|Frequency|Word|Frequency|Word|Frequency|")
        f.write("\n|---|---|---|---|---|---|---|---|\n")
        
        # Adjust for four columns per row
        rows = cursor.fetchall()
        for i in range(0, len(rows), 4):
            row_group = rows[i:i+4]
            f.write("|")
            for row in row_group:
                f.write(f"{row[0]}|{row[1]}|")
            f.write("\n")

        f.write("\n\n")
        
        # Write the parameters
        f.write("Parameters:\n")
        f.write(f"- Batch size: {batch_size}\n")
        f.write(f"- Threshold: {threshold}\n")
        f.write("\n\n")

        # Write the results
        f.write("Generated results:\n\n")
        f.write(f"- Sum of frequency: {sum_frequency}\n")
        f.write(f"- Average of frequency: {avg_frequency}\n")
        f.write(f"- Counting frequency: {counting_frequency}\n")
        f.write(f"- Coverage: {coverage:.2%}\n")
        f.write(f"- Word count: {offset}\n")
        f.write("\n\n")

        f.write("End of report.\n")
        print("Report generated.")

    conn.close()
    return offset
