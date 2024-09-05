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

def getWordFrequencyAnalysis(threshold = 0.82) -> int:
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

    # check out result
    minimum_frequency = 0
    total_frequency_above_threshold = 0
    relative_popularity = 0

    print("Generating report...")
    with open(path.WordFrequencyAnalysis_path, 'w', encoding='utf-8') as f:
        # Write the header
        f.write("# Word frequency analysis\n\n")
        # Write the main report

        f.write("### Top 20% words of best coverage:\n\n")
        f.write("\nThis test to see the effect on the word coverage when eliminating the least frequent words on the overall frequency.\n\n")
        
        # 20/80 method
        factor = 0.20

        # Write the header
        f.write(f"|Min frequency | Total frequency | Number of words | Top {factor * 100}% | Relative Pop. | Absolute Pop. |")
        f.write("\n|---|---|---|---|---|\n")

        for i in range(0, 200, 10):
            total_frequency = cursor.execute(f"SELECT SUM(frequency) FROM word_frequencies WHERE frequency > {i}").fetchone()[0]
            num_words = cursor.execute(f"SELECT COUNT(*) FROM word_frequencies WHERE frequency > {i}").fetchone()[0]
            
            top_percent = round(num_words * factor)
            cursor.execute("SELECT * FROM word_frequencies ORDER BY frequency DESC")
            most_popular_percent = 0
            for _ in range(top_percent):
                most_popular_percent += cursor.fetchone()[1]

            popularity_top_percent = most_popular_percent / total_frequency * 100
            actual_popularity = most_popular_percent / sum_frequency * 100

            if popularity_top_percent > threshold * 100:
                minimum_frequency = i
                total_frequency_above_threshold = total_frequency
                relative_popularity = popularity_top_percent

            f.write(f"| {i} | {total_frequency} | {num_words} | {most_popular_percent} | {popularity_top_percent} | {actual_popularity} |")
        
        # Write the parameters
        f.write("Parameters:\n")
        f.write(f"- Threshold: {threshold}\n")
        f.write("\n\n")

        # Write the results
        f.write("Generated results:\n\n")
        f.write(f"- Sum of frequency: {sum_frequency}\n")
        f.write(f"- Average of frequency: {avg_frequency}\n")
        f.write(f"- Minimum frequency: {minimum_frequency}\n")
        f.write(f"- Total frequency above threshold: {total_frequency_above_threshold}\n")
        f.write(f"- Relative popularity: {relative_popularity}%\n")
        f.write("\n\n")

        f.write("End of report.\n")
        print("Report generated.")
    
    # Copy an portion of the table to another table
    cursor.execute("DROP TABLE IF EXISTS coverage_analysis")
    cursor.execute("""CREATE TABLE coverage_analysis (word TEXT PRIMARY KEY, frequency INTEGER,
                   FOREIGN KEY (word, frequency) REFERENCES word_frequencies(word, frequency))""")
    cursor.execute("""INSERT INTO coverage_analysis
                   SELECT word, frequency FROM word_frequencies
                   ORDER BY frequency DESC
                   WHERE frequency > ?""", (minimum_frequency,))
    
    # Copy

    # Complete transaction
    conn.commit()
    conn.close()
    return cursor.execute("SELECT COUNT(*) FROM coverage_analysis").fetchone()[0]
