import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from sklearn.feature_extraction.text import TfidfVectorizer
import sqlite3
from scipy.sparse import csc_matrix
import re
from modules.path import chunk_database_path
import threading
from queue import Queue
import pickle
import time

def download_nltk():
    print("Downloading NLTK resources...")
    nltk.download('punkt')
    nltk.download('stopwords')
    print("NLTK resources downloaded.")

DATABASE_FILE = chunk_database_path

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

    attempts = 0
    while attempts < 999:
        try:
            cursor.executemany("INSERT INTO tf_idf_data (chunk_id, word_index, tf_idf_value) VALUES (?, ?, ?)", data_list)
            conn.commit()
            break
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                attempts += 1
                time.sleep(0.1)  # Sleep for a short time before retrying
            else:
                raise
        if attempts >= 999:
            print("Failed to store TF-IDF data after 999 attempts due to database lock.")

def store_vectorizer(conn, cursor, vectorizer):
    """Stores the fitted TF-IDF vectorizer in the database."""
    vectorizer_data = pickle.dumps(vectorizer)
    attempts = 0
    while attempts < 999:
        try:
            cursor.execute("INSERT INTO vectorizer_data (data) VALUES (?)", (vectorizer_data,))
            conn.commit()
            break
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e):
                attempts += 1
                time.sleep(0.1)  # Sleep for a short time before retrying
            else:
                raise
        if attempts >= 999:
            print("Failed to store vectorizer data after 999 attempts due to database lock.")

def load_vectorizer(conn, cursor):
    """Loads the fitted TF-IDF vectorizer from the database."""
    cursor.execute("SELECT data FROM vectorizer_data")
    vectorizer_data = cursor.fetchone()
    if vectorizer_data:
        return pickle.loads(vectorizer_data[0])
    else:
        raise Exception("TF-IDF vectorizer data not found in the database.")

def find_most_similar(conn, cursor, query_input, vectorizer):
    """Finds the text chunk most similar to the query based on cosine similarity."""
    query_preprocessed = preprocess_text(query_input)
    query_vector = vectorizer.transform([query_preprocessed])
    
    cursor.execute("SELECT id, chunk_text FROM pdf_chunks")
    text_chunks = cursor.fetchall()
    
    max_similarity = -1
    most_similar_chunk = None
    
    for chunk_id, text_chunk in text_chunks:
        chunk_preprocessed = preprocess_text(text_chunk)
        chunk_vector = vectorizer.transform([chunk_preprocessed])
        similarity = (chunk_vector * query_vector.T).toarray()[0][0]
        if similarity > max_similarity:
            max_similarity = similarity
            most_similar_chunk = text_chunk
    
    return most_similar_chunk, max_similarity

def create_tables(conn, cursor):
    print("Creating tables if they do not exist...")
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
    print("Tables created or already exist.")

def worker(preprocess_queue, store_queue):
    while True:
        text_chunks = preprocess_queue.get()
        if text_chunks is None:
            preprocess_queue.task_done()
            break
        
        print(f"Preprocessing {len(text_chunks)} text chunks...")
        preprocessed_chunks = [preprocess_text(chunk) for chunk in text_chunks]
        vectorizer, tfidf_matrix = create_tfidf_matrix(preprocessed_chunks)
        store_queue.put((text_chunks, tfidf_matrix, vectorizer))
        preprocess_queue.task_done()

def store_worker(store_queue):
    while True:
        text_chunks, tfidf_matrix, vectorizer = store_queue.get()
        if text_chunks is None:
            store_queue.task_done()
            break

        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()

        print(f"Storing TF-IDF data for {len(text_chunks)} text chunks...")
        store_tfidf_data(conn, cursor, text_chunks, tfidf_matrix)

        store_vectorizer(conn, cursor, vectorizer)

        cursor.close()
        conn.close()

        store_queue.task_done()

def preprocess_and_store_text():
    """Function to preprocess text chunks and store them in the database."""
    batch_size = 100
    num_threads = 4  # Adjust based on your CPU cores and load

    preprocess_queue = Queue()
    store_queue = Queue()

    # Start worker threads
    for _ in range(num_threads):
        threading.Thread(target=worker, args=(preprocess_queue, store_queue), daemon=True).start()
        threading.Thread(target=store_worker, args=(store_queue,), daemon=True).start()

    offset = 0

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    print("Connecting to the database...")
    create_tables(conn, cursor)

    while True:
        print(f"Fetching batch starting at offset {offset}...")
        cursor.execute("SELECT chunk_text FROM pdf_chunks ORDER BY id LIMIT ? OFFSET ?", (batch_size, offset))
        rows = cursor.fetchall()
        if not rows:
            print("No more rows to process.")
            break

        text_chunks = [row[0] for row in rows]
        preprocess_queue.put(text_chunks)

        offset += batch_size

    # Wait for all tasks to be done
    preprocess_queue.join()
    store_queue.join()

    # Stop worker threads
    for _ in range(num_threads):
        preprocess_queue.put(None)
        store_queue.put(None)

    cursor.close()
    conn.close()

    print("Finished processing all batches.")

def compute_similarity():
    """Function to get user input and compute similarity with text chunks in the database."""
    print("Connecting to the database...")
    # Connect to the database
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    print("Connected to the database.")

    # Load the fitted vectorizer
    print("Loading the fitted TF-IDF vectorizer...")
    vectorizer = load_vectorizer(conn, cursor)

    # Get user query input
    query_input = input("Enter your query: ")

    print("Finding the most similar text chunk to the query...")
    # Find most similar text chunk
    most_similar_chunk, similarity_score = find_most_similar(conn, cursor, query_input, vectorizer)

    if most_similar_chunk:
        print(f"Most similar chunk: {most_similar_chunk}")
        print(f"Similarity score: {similarity_score}")
    else:
        print("No similar chunk found.")

    # Close connections
    cursor.close()
    conn.close()
    print("Database connection closed.")

if __name__ == "__main__":
    # download_nltk()
    preprocess_and_store_text()
    compute_similarity()
