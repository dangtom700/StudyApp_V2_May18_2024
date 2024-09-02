import argparse
import modules.updateLog as updateLog
import modules.search as search
import modules.extract_text as extract_text
import modules.path as path

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
    parser.add_argument("--precompVector", action= 'store_true', help="Precompute the title vector")
    parser.add_argument("--reorderMaterial", action= 'store_true', help="Categorize PDF files by month and year")
    # very seasonal use
    parser.add_argument("--searchTitle", type=str, help="Search for files in the specified folder path")
    parser.add_argument("--suggestTitle", action= 'store_true', help="Suggest pdf files for an input prompt")
    parser.add_argument("--getNoteReview", action= 'store_true', help="Export a list of notes to review in .md format")

    args = parser.parse_args()

    if args.extractText:
        
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
        extract_text.extract_text(CHUNK_SIZE=chunk_size)
        updateLog.print_and_log("Finished extracting text from PDF files.")
        # extract text from markdown files
        updateLog.print_and_log("Extracting text from markdown files...")
        extract_text.extract_markdown_notes_in_batches(path.study_notes_folder_path, chunk_size=chunk_size)
        updateLog.print_and_log("Finished extracting text from markdown files.")
        # update_database
        updateLog.print_and_log("Updating database from log file...")
        updateLog.store_log_file_to_database(path.log_file_path)
        updateLog.print_and_log("Finished updating database from log file.")

    if args.updateDatabase:
        
        updateLog.print_and_log("Updating database from log file...")
        # create_index_tables
        updateLog.print_and_log("Extracting files from multiple folders")
        folders = [path.pdf_path, path.study_notes_folder_path]
        extensions = [".pdf", ".md"]
        extract_text.create_type_index_table(folders, extensions)
        updateLog.print_and_log("Finished extracting files from multiple folders")
        # announce finish
        updateLog.print_and_log("Finished updating database from log file.")
    
    if args.processWordFreq:
        
        updateLog.print_and_log("Processing word frequencies in chunks...")
        # process word frequency
        extract_text.process_word_frequencies_in_batches()
        # announce finish
        updateLog.print_and_log("Finished processing word frequencies.")

    if args.analyzeWordFreq:
        
        updateLog.log_message(f"Exporting word frequency analysis to 'word_frequency_analysis.md' in {path.WordFrequencyAnalysis_path}...")
        updateLog.print_and_log("Exporting word frequency analysis...")
        search.getWordFrequencyAnalysis(threshold= 0.82)
        updateLog.log_message(f"Finished exporting word frequency analysis to 'word_frequency_analysis.md' in {path.WordFrequencyAnalysis_path}.")

    if args.precompVector:
        
        updateLog.print_and_log("Precomputing title vector...")
        # precompute title vector
        extract_text.precompute_title_vector(database_path=path.chunk_database_path)
        # announce finish
        updateLog.print_and_log("Title vector precomputation complete.")

    if args.reorderMaterial:
        updateLog.print_and_log(f"Exporting reading material to 'Reading Material.md' in {path.ReadingMaterial_path}...")
        updateLog.categorize_pdf_files_by_month_year()
        updateLog.print_and_log(f"Finished exporting reading material to 'Reading Material.md' in {path.ReadingMaterial_path}.")

    # very seasonal use
    if args.searchTitle:
        updateLog.print_and_log(f"Searching for keyword '{args.searchTitle}'...")
        updateLog.print_and_log(f"Searching for files in database...")
        search.searchFileInDatabase(args.searchTitle)
        updateLog.print_and_log(f"Finished search.")

    if args.suggestTitle:
        prompt = input("Enter a prompt: ")
        suggest_number = int(input("Enter the number of suggestions: "))
        updateLog.log_message(f"Prompt: {prompt}")
        updateLog.print_and_log(f"Suggesting {suggest_number} titles...")
        extract_text.suggest_top_titles(path.chunk_database_path,prompt, suggest_number)
        updateLog.print_and_log(f"Finished suggesting titles.")

    if args.getNoteReview:
        updateLog.print_and_log(f"Exporting notes to 'Note Review.md' in {path.Obsidian_noteReview_path}...")
        search.getNoteReviewTask()
        updateLog.print_and_log(f"Finished exporting notes to 'Note Review.md' in {path.Obsidian_noteReview_path}.")

if __name__ == "__main__":
    app()
    # extract_text.download_nltk()
    """
    Typical usage:
    python source/main.py --help
    python source/main.py --extractText
    python source/main.py --updateDatabase
    python source/main.py --searchTitle
    python source/main.py --getNoteReview
    python source/main.py --analyzeWordFreq
    python source/main.py --reorderMaterial
    python source/main.py --processWordFreq
    python source/main.py --precompVector
    python source/main.py --suggestTitle

    full command:
    python source/main.py --extractText --updateDatabase --processWordFreq --analyzeWordFreq
    python source/main.py --precompVector --reorderMaterial
    """