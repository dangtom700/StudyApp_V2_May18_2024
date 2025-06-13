import os
import sqlite3
import re
import nltk
from collections import defaultdict
from shutil import rmtree
from modules.path import chunk_database_path, token_json_path, buffer_json_path, dataset_path, log_file_path
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from concurrent.futures import ThreadPoolExecutor
from json import dump
import string
from functools import partial

# One-time compiled regex pattern
REPEATED_CHAR_PATTERN = re.compile(r"([a-zA-Z])\1{2,}")

# Initialize stemmer and stopwords
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))
banned_word = {
    'what', 'a', 'when', 'with', 'being', 'at', 'was', 'all', 'is',
    'where', 'not', 'off', 'have', 'you', 'she', 'such', 'me',
    'enough', 'out', 'get', 'how', 'them', 'before', 'yours', 'after',
    'above', 'about', 'some', 'up', 'between', 'as', 'got', 'why',
    'are', 'far', 'will', 'down', 'own', 'yourselves', 'his', 'their',
    'in', 'might', 'ought', 'i', 'were', 'he', 'must', 'below', 'to',
    'should', 'shall', 'did', 'nor', 'doing', 'since', 'for', 'my',
    'any', 'same', 't', 'does', 'more', 'also', 'theirselves', 'who',
    'herself', 'and', 'your', 'each', 'ours', 'its', 'few', 'don',
    'itself', 'could', 'over', 'too', 'no', 'most', 'an', 'until',
    'they', 'be', 'only', 'do', 'of', 'it', 'very', 'need', 'done',
    'would', 'may', 'from', 'her', 'near', 'theirs', 'themselves',
    'we', 'through', 'gotten', 's', 'himself', 'ourselves', 'just',
    'us', 'had', 'on', 'been', 'myself', 'yourself', 'him', 'has',
    'hers', 'both', 'can', 'into', 'by', 'the', 'now', 'having', 'other'
}
stop_words.update(banned_word)
stop_words.update(string.punctuation)
stop_words = frozenset(stop_words)  # Optimize stopwords lookup

def ultra_clean_token(text):
    """
    Perform ultra cleaning on a given string by removing leading/trailing spaces, 
    newlines, special characters, and extra spaces. This is a more aggressive 
    version of the clean_text function.

    Parameters
    ----------
    text : str
        The string to be cleaned.

    Returns
    -------
    str
        The cleaned string.
    """
    text = text.strip() # Remove leading/trailing spaces
    text = re.sub(r"\n", " ", text) # Remove newlines
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", text) # Remove special characters
    text = re.sub(r"\s+", " ", text) # Remove extra spaces
    return text

def has_repeats_regex(word):
    """
    Check if a given word has repeated characters (3 or more) with a pre-compiled regex pattern.

    Parameters
    ----------
    word : str
        The word to be checked.

    Returns
    -------
    bool
        Whether the word has repeated characters or not.
    """
    return bool(REPEATED_CHAR_PATTERN.search(word))

def clean_text(text: str):
    # Remove punctuation and convert to lowercase
    """
    Clean a given string by removing punctuation, converting to lowercase, tokenizing, 
    removing stop words, removing words with repeated characters, and stemming. The 
    first and last token of the string are excluded from the cleaning process.

    Parameters
    ----------
    text : str
        The string to be cleaned.

    Returns
    -------
    dict
        A dictionary containing the cleaned tokens as keys and their frequency as values.
    """
    text = re.sub(r'[^\w\s]', '', text).lower()
    text = ultra_clean_token(text)
    # Tokenize text
    tokens = nltk.word_tokenize(text)

    # Initialize filtered tokens
    filtered_tokens = defaultdict(int)

    # Process tokens
    for token in tokens:  # Exclude the first and last token
        if token.isalpha() and token not in stop_words and not has_repeats_regex(token):
            root_word = stemmer.stem(token)
            filtered_tokens[root_word] += 1

    return filtered_tokens

# Retrieve title IDs from the database
def get_title_ids(cursor):
    """
    Retrieve title IDs from the database.

    Parameters
    ----------
    cursor : sqlite3.Cursor
        A database cursor.

    Returns
    -------
    dict
        A dictionary containing title IDs as values and their corresponding file names as keys.
    """

    cursor.execute("SELECT id, file_name FROM file_info WHERE chunk_count > 0")
    return {title[1]: title[0] for title in cursor.fetchall()}

# Retrieve and clean text chunks for a single title using a generator
def retrieve_token_list(title_id, database):
    """
    Retrieve and clean text chunks for a single title using a generator.

    Parameters
    ----------
    title_id : str
        The title ID to retrieve the text chunks for.
    database : str
        The name of the SQLite database to connect to.

    Returns
    -------
    dict
        A dictionary containing the cleaned tokens as keys and their frequency as values.

    Notes
    -----
    This function uses a generator to process each chunk one at a time to minimize memory usage.
    It also handles invalid data and SQLite errors gracefully.
    """
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    clean_text_dict = defaultdict(int)
    try:
        # Retrieve chunks for the title
        cursor.execute("SELECT (chunk_text) FROM pdf_chunks WHERE file_name = ?", (title_id+".txt",))
        chunks = cursor.fetchall()

        # Process each chunk one at a time to minimize memory usage
        for chunk in chunks:
            chunk_result = clean_text(chunk[0])
            for word, freq in chunk_result.items():
                clean_text_dict[word] += freq

    except sqlite3.Error as e:
        print(f"SQLite error while retrieving token list for title ID {title_id}: {e}")
    finally:
        conn.close()  # Ensure the connection is closed

    return clean_text_dict

# Process chunks in batches and store word frequencies in individual JSON files
def process_chunks_in_batches(database, pdf_titles, fetched_result):
    """
    Process chunks in batches and store word frequencies in individual JSON files.

    This function takes a list of title IDs, a dictionary of title IDs to starting IDs and chunk counts, and a connection to a SQLite database.
    It processes chunks in batches and stores word frequencies in individual JSON files in the `token_json_path` folder.
    It also keeps track of the global word frequencies and stores them in a single JSON file after all titles have been processed.
    """
    
    global_word_freq = defaultdict(int)

    # Ensure the directory exists
    os.makedirs(token_json_path, exist_ok=True)

    # Partial function to bind database parameter for parallel processing
    retrieve_func = partial(retrieve_token_list, database=database)

    # Process title IDs in parallel (each thread gets its own connection)
    with ThreadPoolExecutor() as executor:
        for title_id, word_freq in zip(pdf_titles, executor.map(retrieve_func, pdf_titles)):
            if word_freq is None or len(word_freq) == 0:
                continue
            
            # Update global word frequencies
            for word, freq in word_freq.items():
                global_word_freq[word] += freq

            # Dump word frequencies for each title into a separate JSON file immediately
            json_file_path = os.path.join(token_json_path, f'title_{fetched_result[title_id]}.json')
            with open(json_file_path, 'w', encoding='utf-8') as f:
                dump(word_freq, f, ensure_ascii=False, indent=4)

    print("All titles processed and word frequencies stored in individual JSON files.")

    json_global_path = os.path.join(os.getcwd(), 'data', 'global_word_freq.json')
    with open(json_global_path, 'w', encoding='utf-8') as f:
        dump(global_word_freq, f, ensure_ascii=False, indent=4)
    print("Global word frequencies inserted into the database.")

# Retrieve title IDs from JSON files with pattern title_*.json -> *
def get_title_ids_from_json(folder_path):
    """
    Retrieve title IDs from JSON files with pattern title_*.json -> *
    
    Parameters
    ----------
    folder_path : str
        The path to the folder containing the JSON files.
    
    Returns
    -------
    set
        A set of title IDs extracted from the file names.
    """
    title_ids = set()
    for file in os.listdir(folder_path):
        if file.startswith('title_') and file.endswith('.json'):
            title_ids.add(file[6:-5])  # Extract title ID from file name
    return title_ids

# Main function to process word frequencies in batches
def process_word_frequencies_in_batches(reset_state=False, folder_path=token_json_path):
    """
    Process word frequencies in batches and store them in individual JSON files.

    Args:
        reset_state (bool, optional): If True, delete the existing folder and recreate it. Defaults to False.
        folder_path (str, optional): The path to the folder where the JSON files will be saved. Defaults to token_json_path.

    If reset_state is False, the function will check if there are any missing title IDs in the folder and process them. If there are no missing title IDs, the function will print a message and do nothing.
    """
    conn = sqlite3.connect(chunk_database_path, check_same_thread=False)
    cursor = conn.cursor()

    print("Starting batch processing of chunks...")

    os.makedirs(folder_path, exist_ok=True)

    if reset_state:
        if os.path.exists(folder_path):
            rmtree(folder_path)
        os.makedirs(folder_path)
        fetched_result = get_title_ids(cursor)
        pdf_titles = list(fetched_result.keys())
        process_chunks_in_batches(database=chunk_database_path, pdf_titles=pdf_titles, fetched_result=fetched_result)
    else:
        # Retrieve title IDs from the database
        titleID_db = cursor.execute("SELECT id FROM file_info WHERE chunk_count > 0").fetchall()
        titleID_db = set([title[0] for title in titleID_db])
        # Retrieve title IDs from JSON files
        titleID_json = set(get_title_ids_from_json(folder_path))
        # Retrieve title IDs from the complete table of database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_token'")
        if cursor.fetchone():
            titleID_complete = cursor.execute("SELECT DISTINCT file_name FROM file_token").fetchall()
        else:
            titleID_complete = []
        titleID_complete = set([title[0] for title in titleID_complete])
        # Find the difference between the two sets
        titleID_diff = titleID_db - titleID_json - titleID_complete
        # If there are any missing title IDs, process them
        if titleID_diff:
            titleID_diff = list(titleID_diff)
            pdf_titles = [cursor.execute("SELECT file_name FROM file_info WHERE id = ?", (titleID,)).fetchone()[0] for titleID in titleID_diff]
            fetched_result = {title: titleID for title, titleID in zip(pdf_titles, titleID_diff)}
            process_chunks_in_batches(database=chunk_database_path, pdf_titles=pdf_titles, fetched_result=fetched_result)
        else:
            print("All titles have been processed. No new titles to process.")

    print("Processing word frequencies complete.")
    conn.commit()
    conn.close()

# _________________________________________________________________________________
# _________________________________________________________________________________

def promptFindingReference() -> None:
    """Reads in a prompt from a text file, cleans the text, and stores the cleaned
    prompt in a JSON file. The prompt is cleaned by removing punctuation, converting
    to lowercase, tokenizing, removing stop words, removing words with repeated
    characters, and stemming. If the cleaned prompt is empty, a message is printed
    and the function returns early. Otherwise, the cleaned prompt is stored in the
    buffer.json file."""
    def clean_prompt(text: str):
        # Remove punctuation and convert to lowercase
        text = re.sub(r'[^\w\s]', ' ', text).lower()
        text = ultra_clean_token(text)
        # Tokenize text
        tokens = nltk.word_tokenize(text)

        # Initialize filtered tokens
        filtered_tokens = defaultdict(int)

        # Process tokens
        for token in tokens:  # Exclude the first and last token
            if token.isalpha() and token not in stop_words and not has_repeats_regex(token):
                root_word = stemmer.stem(token)
                filtered_tokens[root_word] += 1

        return filtered_tokens
    # Read in from prompt.txt
    with open("PROMPT.txt", "r", encoding="utf-8", errors="ignore") as f:
        prompt = f.readlines()

    prompt = " ".join(prompt)

    # Clean the prompt text
    cleaned_prompt = clean_prompt(prompt)

    # Check if cleaned prompt is empty
    if not cleaned_prompt:
        print("No valid words found in the prompt.")

    # Dump the cleaned prompt to the buffer.json file
    with open(buffer_json_path, "w") as f:
        dump(cleaned_prompt, f, ensure_ascii=False, indent=4)
