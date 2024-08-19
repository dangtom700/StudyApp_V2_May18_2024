"""
	+ Process
		Phase 1: Pre-process words impact in text chunks and titles
			Note: When computing the TF-IDF, to improve the accuracy, times every value by 100 and also limit the decimal place to 16 (subject to test)
		X1) Sort the word frequency table in descending order on the frequency columns (pre-compute the root words population in the text chunk database) and check the max chunk ID to make sure it is under 1950
		X2) Compute in iterations to find the least number of words that cover the most ground in the text chunk database in batches of 100 words, constant incrementing word size of 100 
		X3) Export a report that consists of word coverage iterations, a table of those words with their frequency and inputs & outputs data and a partially duplicated table in the name "word coverage"
		X3.1) Set constant value to reuse for faster computation, such as number of pdf titles, number of chunks, frequency of each root word (suggest to create a table to store constant value)
		4) For each book title, create a table that consists of rows taken from the word coverage table, and columns including chunk IDs of that title to count number of root words. Name [title]_counter
		5) For each [title]_counter, create a table called [title]_analysis, compute the TF-IDF values for each term of each text chunk
		6) Create a table, called "title_TF_IDF" to store the TF-IDF values of each term to the corresponding titles, derived from the corresponding tables
				Note 1: For this step, each word appear in the title has more impact on the title itself, one term in the title (ignoring the stop words) has an impact of 100* term in the text chunk, *subjected to change
				The mathematical expression (number of appearance of the term in text chunks database) + (number of appearance of the term in the title) * 100
				Note 2: If the term does not appear to be a root word of any words in the word coverage, ignore it

		Phase 2: Prompting and compute relevancy
		1) Setting the rules for prompting.
			- The text has to be at least 200 characters long
		2) Process root words in the prompt and count them
		3) Compute the TF-IDF of the prompt
		4) Multiply them to all TF-IDF values in "title_TF_IDF" 
				'''
				[total impact] = [[title list] : 0]
				[for each root word in the prompt]
					[for each title of that root word]
						[binding value] = [TF-IDF of prompt] * [TF-IDF of title]
						total impact [title] += [binding value]
				'''
		5) Rank for the top 10* of the binding TF-IDF values, *subject to change
		6) For each title, perform step 4 and 5 on the [title]_analysis table and concatenate the top ranking chunk of each title
		7) From concatenate vector, output the top 10* chunk with the corresponding title, chunk ID, and the text chunk, *subject to change

	- Recommendation 1: Skipping the zero value for faster computation. Zero appearance of one term, guarantee zero TF-IDF value and zero binding value
	- Recommendation2: Parallelize the processing in phase 1, step 3 to reduce the performance time
"""

import sqlite3
import os
import modules.path as path
from modules.updateLog import log_message

def create_table_for_title_type(cursor: sqlite3.Cursor, title: str, number_of_columns: int) -> None:
	
	chunk_columns = ", ".join([f"chunk {i} INTEGER DEFAULT 0" for i in range(number_of_columns)])

	# Create the counter table with only word and chunk_n columns
	cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS "{title}_counter" (
            word TEXT PRIMARY KEY,
            {chunk_columns}
        );
    ''')

	# Insert word data from word_coverage into the counter table
	cursor.execute(f'''
        INSERT INTO "{title}_counter" (word)
        SELECT word FROM word_coverage;
    ''',)

	# Create the analysis table with word, frequency, and chunk_n columns
	cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS "{title}_analysis" (
            word TEXT PRIMARY KEY,
            frequency INTEGER,
            {chunk_columns}
        );
    ''')

    # Insert word and frequency data from word_coverage into the analysis table
	cursor.execute(f'''
        INSERT INTO "{title}_analysis" (word, frequency)
        SELECT word, frequency FROM word_coverage;
    ''',)

def count_chunk_for_each_title(cursor: sqlite3.Cursor, pdf_file_name: str) -> int:
	return cursor.execute(f"SELECT COUNT(chunk_index) FROM pdf_chunks WHERE pdf_name = ?", (pdf_file_name,)).fetchone()[0]

def batch_collect_row_names(cursor: sqlite3.Cursor, columns_in_comma: str, table_name: str, batch_size: int = 100):
    offset = 0
    columns = columns_in_comma.split(',')
    num_columns = len(columns)

    while True:
        # Execute the query to fetch a batch of rows
        cursor.execute(f"SELECT {columns_in_comma} FROM {table_name} LIMIT ? OFFSET ?", (batch_size, offset))
        rows = cursor.fetchall()

        if not rows:
            break  # No more rows to fetch

        # Yield each row in the desired format
        for row in rows:
            formatted_row = [row[i] for i in range(num_columns)]
            yield formatted_row

        offset += batch_size

def precompute_word_impact():
    
	conn = sqlite3.connect(path.chunk_database_path)
	cursor = conn.cursor()

	max_chunk_id = cursor.execute("SELECT MAX(chunk_index) FROM pdf_chunks").fetchone()[0]
	print(f"Maximum chunk ID: {max_chunk_id}")
	# log_message(f"Maximum chunk ID: {max_chunk_id}")

	if max_chunk_id > 1950:
		print("The maximum chunk ID is greater than 1950. Please check the database.")
		log_message("The maximum chunk ID is greater than 1950. Please check the database.", "ERROR")
		raise ValueError("The maximum chunk ID is greater than 1950. Please check the database.")
	
	NUMBER_OF_PDF_FILES = cursor.execute("SELECT COUNT(*) FROM pdf_list").fetchone()[0]
	print(f"Total number of pdf files: {NUMBER_OF_PDF_FILES}")
	# log_message(f"Total number of pdf files: {NUMBER_OF_PDF_FILES}")

	NUMBER_OF_CHUNKS = cursor.execute("SELECT MAX(id) FROM pdf_chunks").fetchone()[0]
	print(f"Total number of chunks: {NUMBER_OF_CHUNKS}")
	# log_message(f"Total number of chunks: {NUMBER_OF_CHUNKS}")

	for file in batch_collect_row_names(cursor, "id, pdf_path", "pdf_list"):
		pdf_file_name = os.path.basename(file[1])
		chunk_count = count_chunk_for_each_title(cursor, pdf_file_name)
		print(f"Chunk count for {pdf_file_name}: {chunk_count}")
		# log_message(f"Chunk count for {pdf_file_name}: {chunk_count}")
		create_table_for_title_type(cursor, file[0], chunk_count)
		print(f"Table {file[0]} created.")

	conn.commit()
	conn.close()

# Main Flow
precompute_word_impact()