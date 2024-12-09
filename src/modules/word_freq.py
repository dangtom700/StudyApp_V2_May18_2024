import os
import sqlite3
import re
import nltk
from collections import defaultdict
from shutil import rmtree
from modules.path import chunk_database_path, token_json_path, buffer_json_path
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from concurrent.futures import ThreadPoolExecutor
from json import dump

# One-time compiled regex pattern
REPEATED_CHAR_PATTERN = re.compile(r"([a-zA-Z])\1{2,}")
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))
banned_word = {'near', 'do', 'who', 'yourself', 'four', 'then', 'doing', 'himself',
            'two', 'and', 'during', '3.0', 'of', 'were', 'or', 'did', 'gone',
            'said', 'before', 'you', 'when', 'its', 'myself', 'us', 'Zeno', 
            'zero', 'Vernon', 'should', 'far', 'making', 'gets', 'getting', 
            'be', 'how', 'without', 'knowing', 'make', 'seven', 'ours', 'next',
            'very', 'your', 'this', 'eight', 'ought', 'must', 'goes', 'can',
            'them', 'why', 'under', 'ourselves', 'was', 'know', 'nine', 'need',
            '4.0', 'is', 'made', 'one', 'three', 'above', 'herself', 'have',
            'we', 'my', 'over', 'does', 'on', 'yours', 'that', 'would',
            '5.0', 'no', 'may', 'might', 'go', 'are', 'makes', 'for', 'say', 'she', 
            'it', 'becoming', 'a', 'tor', 'could', 'not', 'will', 'into', 'the', 
            'I', 'below', 'yourselves', 'had', 'her', 'his', 'as', 'date', 'by', 
            'hers', 'more', 'even', 'which', '500+', 'got', 'our', 'down', 'him', 
            'lines', 'up', 'an', 'five', 'been', 'being', 'too', 'ten', 'where', 
            'using', 'itself', 'through', 'what', 'so', 'after', 'shall', 'stuff', 
            'they', 'he', 'Americas', 'appsabout', 'to', 'in', 'at', 'due', 'six', 
            'Richard', 'from', 'use', 'me', 'other', 'with', 'get', 'going', 'has', 
            'hello'}
stop_words.update(banned_word)
def has_repeats_regex(word):
    return bool(REPEATED_CHAR_PATTERN.search(word))

def clean_text(text: str):
    # Remove punctuation and convert to lowercase
    text = re.sub(r'[^\w\s]', '', text).lower()

    # Split text into tokens
    tokens = nltk.word_tokenize(text)

    # Define a function to filter tokens
    def pass_conditions(word):
        return (word.isalpha() and 
                not has_repeats_regex(word) and 
                word not in stop_words)

    # Filter tokens based on conditions and apply stemming
    filtered_tokens = defaultdict(int)
    for token in tokens:
        root_word = stemmer.stem(token)
        if pass_conditions(root_word):
            filtered_tokens[root_word] += 1

    return filtered_tokens

# Retrieve title IDs from the database
def get_title_ids(cursor):
    cursor.execute("SELECT id, file_name FROM file_info WHERE chunk_count > 0")
    return {title[1]: title[0] for title in cursor.fetchall()}

# Retrieve and clean text chunks for a single title using a generator
def retrieve_token_list(title_id, database):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT chunk_count, starting_id FROM file_info WHERE file_name = ?", (title_id,))
        result = cursor.fetchone()

        if result is None:
            raise ValueError(f"No data found for title ID: {title_id}")

        chunk_count, start_id = result

        cursor.execute("""
            SELECT chunk_text FROM pdf_chunks
            LIMIT ? OFFSET ?""", (chunk_count, start_id))

        clean_text_dict = defaultdict(int)

        # Process each chunk one at a time to minimize memory usage
        for chunk in cursor:
            chunk_result = clean_text(chunk[0])
            for word, freq in chunk_result.items():
                clean_text_dict[word] += freq

    except Exception as e:
        print(f"Error retrieving token list for title ID {title_id}: {e}")
    finally:
        conn.close()  # Close the connection to avoid memory leaks

    return clean_text_dict

# Process chunks in batches and store word frequencies in individual JSON files
def process_chunks_in_batches(database):
    conn = sqlite3.connect(database)
    cursor = conn.cursor()

    fetched_result = get_title_ids(cursor)
    pdf_titles = list(fetched_result.keys())
    global_word_freq = defaultdict(int)

    # Ensure the directory exists
    os.makedirs(token_json_path, exist_ok=True)

    # Process title IDs in parallel (each thread gets its own connection)
    with ThreadPoolExecutor(max_workers=4) as executor:
        for title_id, word_freq in zip(pdf_titles, executor.map(retrieve_token_list, pdf_titles, [database] * len(pdf_titles))):

            # Update global word frequencies
            for word, freq in word_freq.items():
                global_word_freq[word] += freq

            # Dump word frequencies for each title into a separate JSON file immediately
            json_file_path = os.path.join(token_json_path, f'title_{fetched_result[title_id]}.json')
            with open(json_file_path, 'w', encoding='utf-8') as f:
                dump(word_freq, f, ensure_ascii=False, indent=4)

    print("All titles processed and word frequencies stored in individual JSON files.")

    conn.commit()
    conn.close()

    json_global_path = os.path.join(os.getcwd(), 'data', 'global_word_freq.json')
    with open(json_global_path, 'w', encoding='utf-8') as f:
        dump(global_word_freq, f, ensure_ascii=False, indent=4)
    print("Global word frequencies inserted into the database.")

# Main function to process word frequencies in batches
def process_word_frequencies_in_batches():
    conn = sqlite3.connect(chunk_database_path, check_same_thread=False)
    cursor = conn.cursor()

    def empty_folder(folder_path):
        if os.path.exists(folder_path):
            rmtree(folder_path)
        os.makedirs(folder_path)

    empty_folder(folder_path=token_json_path)

    print("Starting batch processing of chunks...")
    process_chunks_in_batches(database=chunk_database_path)
    print("Processing word frequencies complete.")
    conn.commit()
    conn.close()

def promptFindingReference() -> None:
    # Enter the prompt
    prompt = input("Enter prompt: ")

    # Clean the prompt text
    cleaned_prompt = clean_text(prompt)

    # Check if cleaned prompt is empty
    if not cleaned_prompt:
        print("No valid words found in the prompt.")

    # Dump the cleaned prompt to the buffer.json file
    with open(buffer_json_path, "w") as f:
        dump(cleaned_prompt, f, ensure_ascii=False, indent=4)
