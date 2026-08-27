import argparse
from random import random
import modules.path as path
import modules.word_freq as word_freq
import modules.tf_idf as tf_idf
# import modules.ideation as ideation
import modules.extract_text as extract_text
import modules.pdf_to_txt as pdf_to_txt
import modules.catalog as catalog
import modules.compress_pdf as compress_pdf
import modules.dedupe_pdf as dedupe_pdf
from random import choice
from os import listdir

def app():

    parser = argparse.ArgumentParser(prog="Study Logging and Database",
                                     description="This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day.",
                                     add_help=True,
                                     allow_abbrev=True)
    
    parser.add_argument("--displayHelp", action= 'store_true', help= 'Display help message')
    parser.add_argument("--renameFile", action= 'store_true', help= 'Encode the file name with hashing algorithm')
    parser.add_argument("--dedupePDF", action= 'store_true', help= 'Screen not-yet-renamed PDFs against the library by content, catching a re-download whose copy on disk was already compressed (run before --renameFile)')
    parser.add_argument("--dedupeIncoming", default= None, help= 'With --dedupePDF, the folder of new downloads to screen (default: READING_LIST_PATH itself)')
    parser.add_argument("--dedupeSweep", action= 'store_true', help= 'With --dedupePDF, compare the library against itself instead of screening new files -- for duplicates that are already in it')
    parser.add_argument("--dedupeDryRun", action= 'store_true', help= 'With --dedupePDF, report what would happen and write nothing')
    parser.add_argument("--dedupeDelete", action= 'store_true', help= 'With --dedupePDF, delete duplicates instead of moving them to _duplicates/')
    parser.add_argument("--dedupePreferIncoming", action= 'store_true', help= 'With --dedupePDF, keep the larger copy\'s bytes under the library copy\'s name (upgrades a compressed copy back to the original)')
    parser.add_argument("--dedupeStructural", action= 'store_true', help= 'With --dedupePDF, also act on scans matched by page count and page size alone (reported but not acted on by default)')
    parser.add_argument("--dedupeThreshold", type= float, default= dedupe_pdf.FUZZY_THRESHOLD, help= 'With --dedupePDF, the Jaccard threshold for the fuzzy text tier (default: %(default)s)')
    parser.add_argument("--compressPDF", action= 'store_true', help= 'Compress the PDFs in READING_LIST_PATH in place with Ghostscript (run after --renameFile, before --pdfToText)')
    parser.add_argument("--compressPreset", default= compress_pdf.DEFAULT_PRESET, choices= compress_pdf.PRESETS, help= 'Ghostscript quality preset for --compressPDF (default: %(default)s)')
    parser.add_argument("--compressJobs", type= int, default= 0, help= 'Parallel Ghostscript processes for --compressPDF (default: CPU count - 2)')
    parser.add_argument("--compressDryRun", action= 'store_true', help= 'With --compressPDF, list what would be compressed and write nothing')
    parser.add_argument("--compressForce", action= 'store_true', help= 'With --compressPDF, ignore the log and re-compress files that were already compressed (lossy -- each pass degrades image quality)')
    parser.add_argument("--pdfToText", action= 'store_true', help= 'Convert PDFs in READING_LIST_PATH to .txt files in RAW_DATA_PATH')
    parser.add_argument("--extractText", action= 'store_true', help= 'Chunk .txt files from RAW_DATA_PATH and store in database')
    parser.add_argument("--processWordFreq", action= 'store_true', help="Create index tables and analyze word frequencies all in one")
    parser.add_argument("--tokenizePrompt", action= 'store_true', help="Prompt to find references in full database based on context of search")
    # TF-IDF is computed by the C++ side: word_tokenizer --computeTFIDF
    parser.add_argument("--computeItemMatrix", action= 'store_true', help="Compute item matrix similarity and output comparison table based on TF-IDF")
    parser.add_argument("--topicTokenize", action= 'store_true', help="Tokenize topics and store in database")
    parser.add_argument("--expandTopicSeeds", action= 'store_true', help="With --topicTokenize, grow the topic list with ~50 Datamuse related words (off by default)")
    parser.add_argument("--buildCatalog", action= 'store_true', help="Build the book_catalog table + export catalog.csv/json")
    parser.add_argument("--catalogStats", action= 'store_true', help="Print book_catalog coverage without rebuilding it")
    parser.add_argument("--noProbe", action= 'store_true', help="With --buildCatalog, skip reading page counts from the PDFs (fast metadata-only rebuild)")

    args = parser.parse_args()

    if args.displayHelp:
        print("This project is to meant to store record of learning activities. The files and record of activities are then transfer into database that show user the timeline and activities done in that day. Python is used to extract text from PDF files and store in database. Python also offers a few useful modules to process Natural Language Processing and word processing modules to conviniently analyze word frequencies and word stems to clean up textual data for processing cosine similarity search.")

    # Runs before --renameFile: that is the last moment at which an incoming file is
    # distinguishable from a library file, because it still has its download name
    # rather than a <sha256>.pdf one. Whatever this stage lets through, rename_files
    # then handles exactly as it always did.
    if args.dedupePDF:
        if args.dedupeSweep:
            dedupe_pdf.sweep(dry_run=args.dedupeDryRun,
                             delete=args.dedupeDelete,
                             structural=args.dedupeStructural)
        else:
            dedupe_pdf.dedupe_all(incoming=args.dedupeIncoming,
                                  dry_run=args.dedupeDryRun,
                                  delete=args.dedupeDelete,
                                  prefer_incoming=args.dedupePreferIncoming,
                                  structural=args.dedupeStructural,
                                  threshold=args.dedupeThreshold)

    if args.renameFile:
        extract_text.rename_files(path.pdf_path)

    # Runs before --pdfToText so the text pipeline reads the files it will keep, and
    # after --renameFile so each book's <sha256>.pdf name is the hash of the file as
    # it was downloaded. Compression rewrites content in place without renaming --
    # see modules/compress_pdf.py for why the stem must not change.
    if args.compressPDF:
        compress_pdf.compress_all(preset=args.compressPreset,
                                  jobs=args.compressJobs,
                                  dry_run=args.compressDryRun,
                                  force=args.compressForce)

    if args.pdfToText:
        pdf_to_txt.convert_all()

    if args.extractText: # function is functioning properly
        
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
        # NOTE: text_to_chunks splits by WORDS, not characters -- the sizes described
        # above are the intent, DEFAULT_CHUNK_SIZE is what actually runs. It lives in
        # extract_text so modules/catalog.py can record it as dataset provenance.
        chunk_size = extract_text.DEFAULT_CHUNK_SIZE
        # extract_text
        extract_text.extract_text(CHUNK_SIZE=chunk_size, SOURCE_FOLDER=path.source_data, DB_PATH=path.chunk_database_path, DEST_FOLDER=path.dest_data)
    
    if args.processWordFreq:
        word_freq.process_word_frequencies_in_batches(reset_state=False)

    if args.tokenizePrompt: # function is functioning properly
        word_freq.promptFindingReference()

    if args.computeItemMatrix:
        tf_idf.compute_item_matrix()

    if args.topicTokenize:
        with open('topics.txt', 'r') as f:
            lines = f.readlines()
        TOPICS = set(line.strip() for line in lines if line.strip())

        # Seed expansion is opt-in. Datamuse returns related *vocabulary*, not article
        # titles, so most of what it adds has no Wikipedia page -- it grows topics.txt
        # with dead entries every run. Without this flag --topicTokenize is idempotent:
        # it only processes what topics.txt already lists.
        if args.expandTopicSeeds:
            SeedTopics = choice(list(TOPICS))
            if SeedTopics:
                print(f"Fetching related topics for: {SeedTopics}")
                TOPICS.update(word_freq.get_related_topics(SeedTopics, limit=50))

        word_freq.tokenize_topics(TOPIC_LIST=TOPICS)

    # Read-mostly stage: joins file_info / file_token / tags_full with the real titles
    # from _original_names.json. Runs last because it consumes the topic tags.
    if args.buildCatalog:
        catalog.build_catalog(probe=not args.noProbe)

    if args.catalogStats:
        catalog.catalog_stats()

if __name__ == "__main__":
    app()