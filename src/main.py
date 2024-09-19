import argparse
from datetime import datetime
import modules.updateLog as updateLog
import modules.search as search
import modules.path as path
import modules.extract_text as extract_text
import modules.word_freq as word_freq
import modules.updateDB as updateDB

def app():

    parser = argparse.ArgumentParser(prog="Study Logging and Database",
                                     description="This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.",
                                     add_help=True,
                                     allow_abbrev=True)
    """
    Operation order:
    1. Extract text from PDF files
    2. Update database
    3. Process word frequencies
    4. Analyze word frequencies
    5.1. Count word frequencies according to title
    5.2. Vectorize titles
    6. Categorize reading material
    """
    parser.add_argument("--extractText", action= 'store_true', help= 'Extract text from PDF files and store in database')
    parser.add_argument("--updateDatabase", action= 'store_true', help="Create index tables and analyze word frequencies all in one")
    parser.add_argument("--processWordFreq", action= 'store_true', help="Create index tables and analyze word frequencies all in one")
    parser.add_argument("--analyzeWordFreq", action= 'store_true', help="Export a list of word frequency analysis in .md format")

    args = parser.parse_args()

    if args.extractText: # function is functioning properly
        start_time = datetime.now()
        
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
        updateLog.print_and_log("Extracting text from PDF files...")
        extract_text.extract_text(CHUNK_SIZE=chunk_size, FOLDER_PATH=path.pdf_path, chunk_database_path=path.chunk_database_path)
        updateLog.print_and_log("Finished extracting text from PDF files.")
        # update_database
        updateLog.print_and_log("Updating database from log file...")
        updateLog.store_log_file_to_database(path.log_file_path)
        updateLog.print_and_log("Finished updating database from log file.")
        # announce finish
        updateLog.get_time_performance(start_time, "Text extracting time")

    if args.updateDatabase: # function is functioning properly
        start_time = datetime.now()
        
        updateLog.print_and_log("Update file information to database...")
        # create_index_tables
        updateLog.print_and_log("Extracting files from multiple folders")
        folders = [path.pdf_path, path.study_notes_folder_path]
        extensions = [".pdf", ".md"]
        updateDB.create_type_index_table(folders, extensions)
        updateLog.print_and_log("Finished extracting files from multiple folders")
        # announce finish
        updateLog.get_time_performance(start_time, "Update file information")
    
    if args.processWordFreq: # function is functioning properly
        start_time = datetime.now()
        
        updateLog.print_and_log("Processing word frequencies in chunks...")
        # process word frequency
        word_freq.process_word_frequencies_in_batches()
        # announce finish
        updateLog.get_time_performance(start_time, "Word frequency processing time")

    if args.analyzeWordFreq: # function is functioning properly
        start_time = datetime.now()
        
        updateLog.log_message(f"Exporting word frequency analysis to 'word_frequency_analysis.md' in {path.WordFrequencyAnalysis_path}...")
        updateLog.print_and_log("Exporting word frequency analysis...")
        search.getWordFrequencyAnalysis(threshold= 0.96)
        updateLog.log_message(f"Finished exporting word frequency analysis to 'word_frequency_analysis.md' in {path.WordFrequencyAnalysis_path}.")
        # announce finish
        updateLog.get_time_performance(start_time, "Word frequency analysis")

if __name__ == "__main__":
    app()