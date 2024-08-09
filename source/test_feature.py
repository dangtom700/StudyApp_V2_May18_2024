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

import json # to read the json file
import sqlite3 # to query the database
import modules.path as path # to get the path of the database
import scipy # to compute the dot product

BATCH_SIZE = 100
FILE_PATH = path.WordFrequencyAnalysis_temp_json_path


def create_relevant_text_chunks_table() -> None:
    conn = sqlite3.connect(path.chunk_database_path)
    cursor = conn.cursor()

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

    # Create a table with foreign id and text chunk from pdf chunks table, 
    # and keywords from the first column word frequency table
    cursor.execute("DROP TABLE IF EXISTS relevant_text_chunks")
    
    conn.commit()
    conn.close()