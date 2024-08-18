"""
+ Process: 
		1) Prepare data about the most popular root words that cover the most ground in the text chunk database (text material including books and Markdown notes)
		2) Generate raw data for the most popular root words analysis and get the key of number of most popular keywords to access to the table
		3) Generate dynamic table with IDs, chunk text, list of popular keywords, length of relevance
		4) Set rules for effective prompting
		5) Set computing algorithms and logging inputs, outputs and errors

	- Recommendation 1: Low the dimension of data vector and increase the number of layer of pre-computation
	- Recommendation 2: Since the limit of SQLite table is 2000 columns, it is better to match the prompt to suggested book titles (n << 2000)
	- Recommendation 3: Instead of get the key to retrieve the number of root words that cover the most ground, create a new table that consists of most popular root words
	- Recommendation 4: Compute the word impact, create a table of each book title, with columns are the most popular root words with an additional row of computing the word impact on that title

	+ Revised process
		Phase 1: Pre-process words impact in text chunks and titles
			Note: When computing the TF-IDF, to improve the accuracy, times every value by 100 and also limit the decimal place to 16 (subject to test)
		1) Sort the word frequency table in descending order on the frequency columns (pre-compute the root words population in the text chunk database) and check the max chunk ID to make sure it is under 1950
		2) Compute in iterations to find the least number of words that cover the most ground in the text chunk database in batches of 100 words, constant incrementing word size of 100 
		3) Export a report that consists of word coverage iterations, a table of those words with their frequency and inputs & outputs data and a partially duplicated table in the name "word coverage"
		3.1) Set constant value to reuse for faster computation, such as number of pdf titles, number of chunks, frequency of each root word (suggest to create a table to store constant value)
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