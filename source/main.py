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
    parser.add_argument("--processWordFrequencies", action= 'store_true', help="Create index tables and analyze word frequencies all in one")
    parser.add_argument("--updateDatabase", action= 'store_true', help="Create index tables and analyze word frequencies all in one")
    parser.add_argument("--getTaskList", action= 'store_true', help="Export a list of tasks in .md format")
    parser.add_argument("--searchTitle", type=str, help="Search for files in the specified folder path")
    parser.add_argument("--getNoteReview", action= 'store_true', help="Export a list of notes to review in .md format")
    parser.add_argument("--getWordFrequencyAnalysis", action= 'store_true', help="Export a list of word frequency analysis in .md format")
    parser.add_argument("--categorizeReadingMaterial", action= 'store_true', help="Categorize PDF files by month and year")

    args = parser.parse_args()

    if args.extractText:
        start_time = datetime.now()
        print(f"Extracting text from PDF files...")
        # Adjust parameters
        """
        Small Chunks (50-200 characters): These are useful for quick retrieval 
        of specific information, such as definitions or short facts. They are 
        easy to index and search but may lack context.

        Medium Chunks (200-500 characters): Medium chunks are a balance between 
        detail and brevity, providing enough context to understand a concept 
        without overwhelming the reader. These are often used in study aids or 
        summaries.

        Large Chunks (500-2000 characters): Large chunks are better suited for 
        conveying more complex ideas, detailed explanations, or comprehensive 
        descriptions. They are more challenging to search but provide deeper 
        understanding.
        """
        chunk_size = 2000
        # extract_text
        updateLog.log_message(f"Extracting text from PDF files...")
        extract_pdf.extract_text(CHUNK_SIZE=chunk_size)
        updateLog.log_message(f"Finished extracting text from PDF files.")
        # update_database
        updateLog.log_message(f"Updating database from log file...")
        updateLog.store_log_file_to_database(path.log_file_path)
        updateLog.log_message(f"Finished updating database from log file.")
        # extract text from markdown files
        updateLog.log_message(f"Extracting text from markdown files...")
        extract_note.extract_markdown_notes_in_batches(path.study_notes_folder_path, chunk_size=chunk_size)
        updateLog.log_message(f"Finished extracting text from markdown files.")
        # announce finish
        print(f"Finished updating database from log file.")
        updateLog.log_message(f"Finished updating database from log file.")
        # calculate the total time done
        end_time = datetime.now()
        updateLog.log_message(f"Total time taken: {end_time - start_time}")
        print(f"Total time taken: {end_time - start_time}")
    
    if args.processWordFrequencies:
        start_time = datetime.now()
        print(f"Processing word frequencies in chunks...")
        updateLog.log_message(f"Processing word frequencies in chunks...")
        # peoxwss word frequency
        extract_pdf.process_word_frequencies_in_batches()
        # announce finish
        print(f"Finished processing word frequencies.")
        updateLog.log_message(f"Finished processing word frequencies.")
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

    if args.searchTitle:
        updateLog.log_message(f"Searching for keyword '{args.searchTitle}'...")
        updateLog.log_message(f"Searching for files in database...")
        search.searchFileInDatabase(args.searchTitle)
        updateLog.log_message(f"Finished search.")

    if args.getNoteReview:
        updateLog.log_message(f"Exporting notes to 'Note Review.md' in {path.Obsidian_noteReview_path}...")
        search.getNoteReviewTask()
        updateLog.log_message(f"Finished exporting notes to 'Note Review.md' in {path.Obsidian_noteReview_path}.")

    if args.getWordFrequencyAnalysis:
        updateLog.log_message(f"Exporting word frequency analysis to 'word_frequency_analysis.md' in {path.WordFrequencyAnalysis_path}...")
        search.getWordFrequencyAnalysis()
        updateLog.log_message(f"Finished exporting word frequency analysis to 'word_frequency_analysis.md' in {path.WordFrequencyAnalysis_path}.")

    if args.categorizeReadingMaterial:
        updateLog.log_message(f"Exporting reading material to 'Reading Material.md' in {path.ReadingMaterial_path}...")
        updateLog.categorize_pdf_files_by_month_year()
        updateLog.log_message(f"Finished exporting reading material to 'Reading Material.md' in {path.ReadingMaterial_path}.")

if __name__ == "__main__":
    app()
    # extract_pdf.download_nltk()
    # search.create_task_list_in_time_range(datetime(2024, 8, 1), datetime(2024, 10, 31))
    """
    Typical usage:
    python source/main.py --help
    python source/main.py --extractText
    python source/main.py --updateDatabase
    python source/main.py --getTaskList
    python source/main.py --searchTitle
    python source/main.py --getNoteReview
    python source/main.py --getWordFrequencyAnalysis
    python source/main.py --categorizeReadingMaterial
    python source/main.py --processWordFrequencies

    python source/main.py --extractText --processWordFrequencies --updateDatabase --getWordFrequencyAnalysis --categorizeReadingMaterial
    python source/main.py --extractText --processWordFrequencies --updateDatabase --getWordFrequencyAnalysis
    python source/main.py --extractText --processWordFrequencies --getWordFrequencyAnalysis
    """