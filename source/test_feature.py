"""
Pre-set the most popular words as the parameters to compute the text chunk
relevance using dot product for vector similarity.

The equation for similarity is:
            a * b = |a| * |b| * cos(angle between a and b)
            with a and b being unit vectors
            => a * b = cos(angle between a and b)

1. Using the words provided in the json file, set a list of parameters for all the 
text chunks.
2. Count the number of times each word appears in the text chunks.
(Text chunks are extracted from database)
3. Compute the magnitude of the vector for each text chunk in a separate list.
Convert it to unit vector.
4. The second vector is the input prompt is vectorized with the same parameters.
5. Compute the dot product of the two vectors.
"""

"""
Create a table for computing the word frequency of each text chunk and the title
of relevant text chunks.

Structure of the table:
id | text chunk    | keyword 1| keyword 2| ... | keyword n| relevance score
1  | text chunk 1  | 0       | 0        | ... | 0        | sqrt(sum{[1->n]}^2)
2  | text chunk 2  | 0       | 0        | ... | 0        | sqrt(sum{[1->n]}^2)

In a separate table, compute the relevance score for each title to the prompt.
n  | title         |sum{}    |sum{}     | ... |sum{}     | sqrt(sum{[1->n]}^2)
calculate the sum of all the frequency that each keyword appears in the text chunks.
"""

import sqlite3 # to query the database
import modules.path as path # to get the path of the database
import numpy # to compute the dot product
import modules.search as search # to query the database
from modules.updateLog import log_message # to log the message

import sqlite3

def create_relevant_text_chunks_table(batch_size=100, file_path= path.chunk_database_path) -> None:
    # Word population is collected from the generated word frequency analysis
    word_population = 3000 #search.getWordFrequencyAnalysis()

    conn = sqlite3.connect(file_path)
    cursor = conn.cursor()

    # Drop the table if it exists
    cursor.execute("DROP TABLE IF EXISTS relevant_text_chunks")

    # Create the table with a primary key and the vecLen column
    cursor.execute("""
    CREATE TABLE relevant_text_chunks (
        text_chunk TEXT PRIMARY KEY,
        vecLen REAL DEFAULT 0.0
    )
    """)

    def retrieve_words_in_batches():
        for i in range(0, word_population, batch_size):
            cursor.execute("SELECT word FROM word_frequencies ORDER BY frequency DESC LIMIT ? OFFSET ?", (batch_size, i))
            yield [row[0] for row in cursor.fetchall()]

    def add_columns_to_table():
        for words in retrieve_words_in_batches():
            for word in words:
                cursor.execute(f"ALTER TABLE relevant_text_chunks ADD COLUMN '{word}' INTEGER DEFAULT 0")

    # Add the columns for each word
    add_columns_to_table()

    # Foreign keys are generally added when creating the table, so it's already handled above
    # Foreign keys:
    # - id references pdf_chunks(id)
    # - text_chunk references pdf_chunks(chunk_text)

    # Commit the changes
    conn.commit()
    conn.close()
    print("Relevant text chunks table created.")

create_relevant_text_chunks_table()
