import argparse
import modules.updateLog as updateLog
import modules.extract_pdf as extract_pdf
import modules.search as search
import modules.extract_note as extract_note
import modules.path as path
from datetime import datetime


def app():

    parser = argparse.ArgumentParser(prog="Study Logging and Database",
                                     description="This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.",
                                     add_help=True,
                                     allow_abbrev=True)
    
    parser.add_argument("--extractText", action= 'store_true', help= 'Extract text from PDF files and store in database')
    parser.add_argument("--updateDatabase", action= 'store_true', help="Create index tables and analyze word frequencies all in one")
    parser.add_argument("--getTaskList", action= 'store_true', help="Export a list of tasks in .md format")
    parser.add_argument("--searchDatabase", type=str, help="Search for files in the specified folder path")

    args = parser.parse_args()

    if args.extractText:
        start_time = datetime.now()
        updateLog.log_message(f"Extracting text from PDF files...")
        # extract_text
        updateLog.log_message(f"Extracting text from PDF files...")
        extract_pdf.extract_text()
        updateLog.log_message(f"Finished extracting text from PDF files.")
        # process_word_frequencies
        updateLog.log_message(f"Processing word frequencies in chunks...")
        extract_pdf.process_word_frequencies_in_batches()
        updateLog.log_message(f"Finished processing word frequencies.")
        # update_database
        updateLog.log_message(f"Updating database from log file...")
        updateLog.store_log_file_to_database(path.log_file_path)
        updateLog.log_message(f"Finished updating database from log file.")
        # announce finish
        print(f"Finished updating database from log file.")
        updateLog.log_message(f"Finished updating database from log file.")
        # calculate the total time done
        end_time = datetime.now()
        updateLog.log_message(f"Total time taken: {end_time - start_time}")
        print(f"Total time taken: {end_time - start_time}")

    if args.updateDatabase:
        start_time = datetime.now()
        updateLog.log_message(f"Updating database from log file...")
        # create_index_tables
        updateLog.log_message(f"Extracting notes from PDF files...")
        extract_note.create_type_index_table(path.pdf_path, ".pdf", "pdf")
        extract_note.create_type_index_table(path.study_notes_folder_path, ".md", "note")
        updateLog.log_message(f"Finished extracting notes from PDF files.")
        # update task list record
        updateLog.log_message(f"Updating task list record...")
        search.processDataFromTaskListFile()
        updateLog.log_message(f"Finished updating task list record.")
        # announce finish
        print(f"Finished updating database from log file.")
        updateLog.log_message(f"Finished updating database from log file.")
        # calculate the total time done
        end_time = datetime.now()
        updateLog.log_message(f"Total time taken: {end_time - start_time}")
        print(f"Total time taken: {end_time - start_time}")

    if args.getTaskList:
        updateLog.log_message(f"Exporting task list to 'Task List.md' in {path.Obsidian_taskList_path}...")
        search.getTaskListFromDatabase()
        updateLog.log_message(f"Finished exporting task list to 'Task List.md' in {path.Obsidian_taskList_path}.")

    if args.searchDatabase:
        updateLog.log_message(f"Searching for keyword '{args.searchDatabase}'...")
        updateLog.log_message(f"Searching for files in database...")
        search.searchFileInDatabase(args.searchDatabase)
        updateLog.log_message(f"Finished search.")

if __name__ == "__main__":
    app()