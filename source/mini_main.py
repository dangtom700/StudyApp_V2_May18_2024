import modules.search as search
import modules.updateLog as updateLog
import modules.extract_note as extract_note
import modules.path as path
from datetime import datetime
import argparse

def app():
    parser = argparse.ArgumentParser(prog="Mini Study Assistant",
                                     description="This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.",
                                     add_help=True,
                                     allow_abbrev=True)
    
    parser.add_argument("--updateDatabase", action= 'store_true', help="Create index tables and analyze word frequencies all in one")
    parser.add_argument("--getTaskList", action= 'store_true', help="Export a list of tasks in .md format")
    parser.add_argument("--getNoteReview", action= 'store_true', help="Export a list of notes to review in .md format")

    args = parser.parse_args()

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


    if args.getNoteReview:
        updateLog.log_message(f"Exporting notes to 'Note Review.md' in {path.Obsidian_noteReview_path}...")
        search.getNoteReviewTask()
        updateLog.log_message(f"Finished exporting notes to 'Note Review.md' in {path.Obsidian_noteReview_path}.")

if __name__ == "__main__":
    app()
    # updateLog.create_cs_file(path.pdf_path, ".pdf")
    # updateLog.create_cs_file(path.study_notes_folder_path, ".md")
    # updateLog.categorize_pdf_files_by_month_year()