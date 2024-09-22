import sqlite3
import colorama
import datetime
import modules.path as path
from modules.updateLog import print_and_log

def mirrorFile_to_destination(source: str, destination: str) -> None:
    with open(source, 'r', encoding='utf-8') as read_obj, open(destination, 'w', encoding='utf-8') as write_obj:
        for line in read_obj:
            write_obj.write(line)

def searchFileInDatabase(keyword: str) -> None:
    try:
        conn = sqlite3.connect('data\\chunks.db')
        cursor = conn.cursor()

        cursor.execute(f"SELECT file_name FROM file_list WHERE file_name LIKE ?", (f'%{keyword}%',))
        result = cursor.fetchall()

        print(f"{colorama.Fore.GREEN}{type.capitalize()} Files containing '{keyword}':{colorama.Style.RESET_ALL}\n")
        # print(f"Files containing '{keyword}':\n")
        for file_name in result:
            print(f"- {colorama.Fore.BLUE}{file_name[0]}{colorama.Style.RESET_ALL}\n")
            # print(f"- {file_name[0]}\n")

    except sqlite3.Error as e:
        print(f"Error searching files in database: {e}")
    finally:
        if conn:
            conn.close()


def randomizeNoteList(count: int = 3) -> list:
    conn = sqlite3.connect(path.chunk_database_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT file_name FROM file_list WHERE file_type = 'md' ORDER BY RANDOM() LIMIT {count}")
    result = cursor.fetchall()
    conn.close()
    result = [note[0] for note in result]
    print_and_log(f"Note list randomized: {result}")
    return result

def exportNoteReviewTask(note_list: list, date: str) -> None:
    with open (path.Obsidian_noteReview_path, 'a', encoding='utf-8') as f:
        f.write(f"\n[[{date}]]\n\n")
        for note in note_list:
            f.write(f"- {note}\n")
    print_and_log("Note review task exported.")
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

    print_and_log("Modified study log template exported to 'Review' folder.")

def getNoteReviewTask() -> None:
    note_list = randomizeNoteList()
    date = datetime.datetime.now().strftime("%b_%d_%Y")
    exportNoteReviewTask(note_list, date)
    exportStudyLogTemplate(note_list, date)

import sqlite3

def getWordFrequencyAnalysis(BATCH_SIZE=1000, threshold=0.96) -> int:
    # Connect to the database
    conn = sqlite3.connect(path.chunk_database_path)
    cursor = conn.cursor()

    # Get the total sum of frequencies
    total_frequency = cursor.execute("SELECT SUM(frequency) FROM word_frequencies").fetchone()[0]
    print(f"Total frequency: {total_frequency}")

    # Initialize batch processing variables
    inserted_sum = 0
    offset = 0

    # Threshold limit based on the total frequency
    threshold_value = total_frequency * threshold

    # Create the coverage_analysis table
    cursor.execute("DROP TABLE IF EXISTS coverage_analysis")
    cursor.execute("""
        CREATE TABLE coverage_analysis (
            word TEXT PRIMARY KEY, 
            frequency INTEGER,
            FOREIGN KEY (word, frequency) REFERENCES word_frequencies(word, frequency)
        )
    """)

    # Loop to insert rows in batches of 1000 and check the cumulative frequency
    while inserted_sum < threshold_value:
        # Select the next batch of 1000 rows
        rows = cursor.execute("""
            SELECT word, frequency FROM word_frequencies 
            ORDER BY frequency DESC 
            LIMIT ? OFFSET ?
        """, (BATCH_SIZE, offset)).fetchall()

        if not rows:
            # If no more rows are available, break the loop
            break

        # Insert the current batch into the coverage_analysis table
        cursor.executemany("""
            INSERT INTO coverage_analysis (word, frequency) 
            VALUES (?, ?)
        """, rows)

        # Update the sum of the inserted frequencies
        batch_sum = sum(row[1] for row in rows)
        inserted_sum += batch_sum
        print(f"Inserted batch sum: {batch_sum}, Total inserted sum: {inserted_sum}")

        # Move the offset for the next batch
        offset += BATCH_SIZE

    # Get the number of rows inserted into the coverage_analysis table
    rows_inserted = cursor.execute("SELECT COUNT(*) FROM coverage_analysis").fetchone()[0]

    # Complete transaction and close the connection
    conn.commit()
    conn.close()

    return rows_inserted

