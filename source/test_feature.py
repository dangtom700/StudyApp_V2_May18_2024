def download_nltk():
    import nltk
    nltk.download('punkt')
    nltk.download('stopwords')

from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
import sqlite3
from scipy.sparse import csc_matrix
import re

# Database connection details (replace with your own)
DATABASE_FILE = 'your_database.db'


def preprocess_text(text):
    """Preprocesses text by lowercasing, removing punctuation, and stop words."""
    text = re.sub(r'[^\w\s]', '', text)  # Remove punctuation
    tokens = text.split()
    stop_words = set(stopwords.words('english'))
    tokens = [w for w in tokens if not w in stop_words]
    stemmer = PorterStemmer()
    tokens = [stemmer.stem(item) for item in tokens]
    return " ".join(tokens)


def create_tfidf_matrix(text_chunks):
    """Creates a TF-IDF matrix from a list of preprocessed text chunks."""
    vectorizer = TfidfVectorizer()
    vectorizer.fit(text_chunks)
    return vectorizer, vectorizer.transform(text_chunks)


def store_tfidf_data(conn, cursor, text_chunks, tfidf_matrix):
    """Stores TF-IDF data in a sparse format using SQLite3."""
    sparse_matrix = csc_matrix(tfidf_matrix)
    data_list = []
    indptr_list = sparse_matrix.indptr.tolist()
    for chunk_id, chunk_start, chunk_end in zip(range(len(text_chunks)), indptr_list[:-1], indptr_list[1:]):
        data_list.extend(zip([chunk_id] * (chunk_end - chunk_start), sparse_matrix.indices[chunk_start:chunk_end], sparse_matrix.data[chunk_start:chunk_end]))

    cursor.executemany("INSERT INTO tf_idf_data (chunk_id, word_index, tf_idf_value) VALUES (?, ?, ?)", data_list)
    conn.commit()


def find_most_similar(conn, cursor, query_input):
    """Finds the text chunk most similar to the query based on cosine similarity."""
    query_preprocessed = preprocess_text(query_input)
    cursor.execute("""SELECT vectorizer.* FROM sqlite_master WHERE type='table' AND name='vectorizer_data'""")
    vectorizer_data = cursor.fetchone()
    if not vectorizer_data:
        raise Exception("TF-IDF vectorizer data not found in the database.")

    # Load vocabulary from the database (replace with your data retrieval logic)
    vocabulary = ...  # Load vocabulary from vectorizer_data table

    # Convert query to TF-IDF vector (replace with your logic based on vocabulary)
    query_vector = ...

    cursor.execute("""
    WITH relevant_chunks AS (
        SELECT tc.id AS chunk_id
        FROM text_chunks tc
        WHERE tc.text LIKE ?  -- Replace with your keyword matching logic
    )
    SELECT rc.chunk_id,
            COSINE_SIMILARITY((SELECT tfidf.tf_idf_value
                                FROM tf_idf_data tfidf
                                WHERE tfidf.chunk_id = rc.chunk_id
                                ORDER BY tfidf.word_index ASC),
                            ?) AS similarity
    FROM relevant_chunks rc,
        UNNEST(?) AS chunk_indptr
    WHERE chunk_indptr >= LAG(chunk_indptr) OVER (ORDER BY rc.chunk_id)
        AND chunk_indptr < LEAD(chunk_indptr) OVER (ORDER BY rc.chunk_id)
    ORDER BY similarity DESC
    LIMIT 1;""", (f"%{query_preprocessed}%", query_vector, indptr_list))

    result = cursor.fetchone()
    if result:
        return text_chunks[result[0]], result[1]  # Chunk text and similarity score
    else:
        return None, None
    
def create_tables(conn, cursor):
    cursor.execute('''CREATE TABLE IF NOT EXISTS tf_idf_data (
                      chunk_id INTEGER,
                      word_index INTEGER,
                      tf_idf_value REAL,
                      FOREIGN KEY (chunk_id) REFERENCES text_chunks(id)
                  )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS vectorizer_data (  -- Optional for storing vocabulary
                        data BLOB  -- Replace with appropriate data type for your vocabulary storage
                    )''')
    conn.commit()

def main():
    """Main function to preprocess text chunks, create TF-IDF vectors, store them, and find most similar chunk."""

    # Connect to the database
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Create tables if they don't exist
    create_tables(conn, cursor)

    # Load or prepare your text chunks (replace with your data source)
    text_chunks = ["This is the first text chunk.", "This is the second text chunk about machine learning.", "This is another text chunk with some overlap."]

    # Preprocess text chunks
    preprocessed_chunks = [preprocess_text(chunk) for chunk in text_chunks]

    # Create TF-IDF matrix
    vectorizer, tfidf_matrix = create_tfidf_matrix(preprocessed_chunks)

    # Store TF-IDF data (optional: store vectorizer data if needed)
    store_tfidf_data(conn, cursor, text_chunks, tfidf_matrix)

    # Get user query input
    query_input = input("Enter your query: ")

    # Find most similar text chunk
    most_similar_chunk, similarity_score = find_most_similar(conn, cursor, query_input)

    if most_similar_chunk:
        print(f"Most similar chunk: {most_similar_chunk}")
        print(f"Similarity score: {similarity_score}")
    else:
        print("No similar chunk found.")

    # Close connections
    cursor.close()
    conn.close()


if __name__ == "__main__":
  main()