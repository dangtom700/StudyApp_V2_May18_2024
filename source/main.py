import argparse
import modules.updateLog as updateLog
import modules.extract_pdf as extract_pdf
import modules.search as search
import modules.extract_note as extract_note
import modules.path as path


def app():

    parser = argparse.ArgumentParser(prog="Study Logging and Database",
                                     description="This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.",
                                     add_help=True,
                                     allow_abbrev=True)
    
    parser.add_argument("--extractText", action= 'store_true', help="Extract text from PDF files")
    parser.add_argument("--updateLog", action= 'store_true', help="Update log of application")
    parser.add_argument("--createIndexTables", action= 'store_true', help="Create index tables for notes and pdf files")
    parser.add_argument("--processWordFrequencies", action= 'store_true', help="Process word frequencies in chunks")
    parser.add_argument("--getTaskList", action= 'store_true', help="Export a list of tasks in .md format")
    parser.add_argument("--searchDatabase", type=str, help="Search for files in the specified folder path")

    args = parser.parse_args()

    if args.extractText:
        updateLog.log_message(f"Extracting text from PDF files...")
        extract_pdf.extract_text()
        updateLog.log_message(f"Finished extracting text from PDF files.")

    if args.updateLog:
        updateLog.log_message(f"Updating log file...")
        updateLog.store_log_file_to_database(path.log_file_path)
        print(f"Finished updating log file.")

    if args.createIndexTables:
        updateLog.log_message(f"Extracting notes from PDF files...")
        extract_note.create_type_index_table(path.pdf_path, ".pdf", "pdf")
        extract_note.create_type_index_table(path.study_notes_folder_path, ".md", "note")
        updateLog.log_message(f"Finished extracting notes from PDF files.")

    if args.processWordFrequencies:
        updateLog.log_message(f"Processing word frequencies in chunks...")
        extract_pdf.process_word_frequencies_in_batches()
        updateLog.log_message(f"Finished processing word frequencies.")

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