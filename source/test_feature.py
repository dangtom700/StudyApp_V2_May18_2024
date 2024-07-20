import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import sqlite3
from data.path import chunk_database_path

import re
from collections import Counter
from sklearn.feature_extraction.text import CountVectorizer
from scipy.sparse import csr_matrix

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
    return tokens

# Sample documents
conn = sqlite3.connect(DATABASE_FILE)
cursor = conn.cursor()
cursor.execute("SELECT chunk_text FROM pdf_chunks ORDER BY RANDOM() LIMIT 5;")
documents = [row[0] for row in cursor.fetchall()]
conn.close()

# Preprocessing function
def preprocess(text):
    # Convert to lowercase
    text = text.lower()
    # Remove punctuation
    text = re.sub(r'\W+', ' ', text)
    # Tokenize
    words = text.split()
    return words

# Setup table to store dense matrix
def setup_table_dense_matrix(cursor):
    cursor.execute("DROP TABLE IF EXISTS dense_matrix")
    cursor.execute("CREATE TABLE dense_matrix (index INTEGER FOREIGN KEY, word TEXT, frequency INTEGER)")

# Preprocess documents
preprocessed_docs = [' '.join(preprocess_text(doc)) for doc in documents]

# Creating term-frequency vectors using sklearn's CountVectorizer
vectorizer = CountVectorizer()
X = vectorizer.fit_transform(preprocessed_docs)

# Converting to sparse matrix representation
sparse_matrix = csr_matrix(X)

# Printing the sparse matrix
print("Sparse Matrix (TF):\n", sparse_matrix)

# For better visualization
print("Dense Representation:\n", sparse_matrix.todense())
print(type(sparse_matrix.todense()))
print("Vocabulary:\n", vectorizer.get_feature_names_out())
print(type(vectorizer.get_feature_names_out()))
