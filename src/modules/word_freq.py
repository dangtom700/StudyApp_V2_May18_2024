import os
import sqlite3
import re
import nltk
from collections import defaultdict
from shutil import rmtree
from modules import schema
from modules.path import chunk_database_path, token_json_path, buffer_json_path, pdf_path, data_folder
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
from concurrent.futures import ThreadPoolExecutor, as_completed
from json import dump
import string
import requests
from functools import partial
from pathlib import Path
from typing import Optional
import time
from itertools import permutations
import hashlib
from threading import Lock
from collections import deque

# Configurations and constants
WIKI_FOLDER = Path("wiki_topics")
PROMPT_FILE = Path("Prompt.txt")
OUTPUT_FILE = Path("outputPrompt.txt")
API_URL = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "TopicDatasetBuilder/1.0 ()"}
CONFIG = {
    # Resolved from .env (READING_LIST_PATH) via modules.path -- never hardcode a drive.
    "DB_PATH": Path(chunk_database_path),
    "SOURCE_FOLDER": Path(pdf_path),
    "NOTES_FOLDER_NAME": "notes",
}
not_found_topics_csv = Path(data_folder) / "not_found_topics.txt"
CONFIG["DESTINATION_FOLDER"] = CONFIG["SOURCE_FOLDER"] / CONFIG["NOTES_FOLDER_NAME"]

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

    print(f"Complete {title_id}")

    return clean_text_dict

# Process chunks in batches and store word frequencies in individual JSON files
def process_chunks_in_batches(database, pdf_titles, fetched_result):
    """
    Process chunks in batches and store word frequencies in individual JSON files.

    This function takes a list of title IDs, a dictionary of title IDs to starting IDs and chunk counts, and a connection to a SQLite database.
    It processes chunks in batches and stores word frequencies in individual JSON files in the `token_json_path` folder.
    It also keeps track of the global word frequencies and stores them in a single JSON file after all titles have been processed.
    """

    # Ensure the directory exists
    os.makedirs(token_json_path, exist_ok=True)

    # Partial function to bind database parameter for parallel processing
    retrieve_func = partial(retrieve_token_list, database=database)

    # Process title IDs in parallel (each thread gets its own connection)
    with ThreadPoolExecutor() as executor:
        for title_id, word_freq in zip(pdf_titles, executor.map(retrieve_func, pdf_titles)):
            if word_freq is None or len(word_freq) == 0:
                continue

            # Dump word frequencies for each title into a separate JSON file immediately
            json_file_path = os.path.join(token_json_path, f'title_{fetched_result[title_id]}.json')
            with open(json_file_path, 'w', encoding='utf-8') as f:
                dump(word_freq, f, ensure_ascii=False, indent=4)

    print("All titles processed and word frequencies stored in individual JSON files.")

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
    # Check if file_token table exists -> bool
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_token';")
    table_exists = cursor.fetchone() is not None

    if reset_state and not table_exists:
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
        if table_exists:
            # Retrieve completed title IDs from the database
            titleID_complete = cursor.execute("SELECT file_name FROM file_token").fetchall()
            titleID_complete = set([title[0].removeprefix("title_") for title in titleID_complete])
        else:
            titleID_complete = set()
        # Find the difference between the two sets
        titleID_diff = titleID_db.difference(titleID_json).difference(titleID_complete)
        print(f"{len(titleID_db)} title IDs in database, {len(titleID_json)} title IDs in JSON files, {len(titleID_complete)} completed title IDs.")
        print(f"Found {len(titleID_diff)} missing title IDs to process.")
        # If there are any missing title IDs, process them
        if titleID_diff:
            titleID_diff = list(titleID_diff)
            pdf_titles = [cursor.execute("SELECT file_name FROM file_info WHERE id = ? ORDER BY chunk_count", (titleID,)).fetchone()[0] for titleID in titleID_diff]
            fetched_result = {title: titleID for title, titleID in zip(pdf_titles, titleID_diff)}
            process_chunks_in_batches(database=chunk_database_path, pdf_titles=pdf_titles, fetched_result=fetched_result)
        else:
            print("All titles have been processed. No new titles to process.")

    print("Processing word frequencies complete.")
    conn.commit()
    conn.close()

def setup_database(conn, reset = False):
    """Prepare topic_token, the table --topicTokenize owns.

    The DDL lives in config/schema.sql; see src/modules/schema.py."""
    if reset:
        schema.reset(conn, ["topic_token"])
    else:
        schema.apply(conn)

def clean_filename(name: str) -> str:
    return re.sub(r"[^\w\-. ]", "_", name)

# Outcomes of a single article fetch. The distinction matters: a topic is only
# ever written to not_found_topics.txt (a permanent blacklist) when Wikipedia
# positively reports the page as missing. A throttled or failed request tells us
# nothing about whether the article exists, so it must never blacklist a topic.
FETCH_OK = "ok"
FETCH_MISSING = "missing"
FETCH_UNAVAILABLE = "unavailable"

MAX_FETCH_ATTEMPTS = 4
INITIAL_BACKOFF = 2.0

# One session for the whole module: connection reuse keeps us well inside
# Wikipedia's rate limits and cuts per-request TLS overhead.
_session = requests.Session()
_session.headers.update(HEADERS)

# Requests are spaced globally rather than per-thread, so raising max_workers
# cannot accidentally raise the request rate.
_rate_lock = Lock()
_last_request = 0.0
_min_interval = 0.5

def set_request_interval(seconds: float):
    """Set the minimum spacing between outbound API requests (all threads)."""
    global _min_interval
    _min_interval = max(0.0, seconds)

def _throttle():
    """Block until at least _min_interval has passed since the last request."""
    global _last_request
    with _rate_lock:
        wait = _min_interval - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()

def _api_get(url: str, params: dict, timeout: int = 30):
    """
    Rate-limited GET with backoff on throttling (429) and server errors (5xx).
    Returns a Response on success, or None if it never got through.
    """
    backoff = INITIAL_BACKOFF

    for attempt in range(MAX_FETCH_ATTEMPTS):
        _throttle()
        try:
            response = _session.get(url, params=params, timeout=timeout)

            if response.status_code == 429 or response.status_code >= 500:
                # Honour Retry-After when the server sends it, else back off.
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else backoff
                if attempt < MAX_FETCH_ATTEMPTS - 1:
                    time.sleep(delay)
                    backoff *= 2
                continue

            response.raise_for_status()
            return response

        except requests.RequestException:
            if attempt < MAX_FETCH_ATTEMPTS - 1:
                time.sleep(backoff)
                backoff *= 2

    return None

def fetch_article(title: str) -> tuple[Optional[str], str]:
    """
    Fetch the plain-text extract of a Wikipedia article.

    Returns
    -------
    tuple[Optional[str], str]
        (text, FETCH_OK)          - article retrieved
        (None, FETCH_MISSING)     - Wikipedia reports no such page; safe to blacklist
        (None, FETCH_UNAVAILABLE) - throttled/unreachable; retry later, do NOT blacklist
    """
    response = _api_get(
        API_URL,
        {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "extracts",
            "explaintext": True,
            "redirects": 1,
        },
        timeout=30,
    )

    if response is None:
        return None, FETCH_UNAVAILABLE

    try:
        pages = response.json().get("query", {}).get("pages", {})
    except ValueError:
        return None, FETCH_UNAVAILABLE

    page = next(iter(pages.values()), {})

    if "missing" in page:
        return None, FETCH_MISSING

    return page.get("extract", ""), FETCH_OK

def get_random_wikipedia_topics(limit=10):
    """Fetch random article titles from Wikipedia."""
    params = {
        "action": "query",
        "format": "json",
        "list": "random",
        "rnnamespace": 0, # Only main articles
        "rnlimit": limit
    }
    response = _api_get(API_URL, params)
    if response is None:
        print("Error fetching random topics from Wikipedia: request did not get through.")
        return set()
    try:
        data = response.json()
        return {item["title"] for item in data.get("query", {}).get("random", [])}
    except Exception as e:
        print(f"Error fetching random topics from Wikipedia: {e}")
        return set()

def get_related_topics(seed: str, limit=50):
    """Fetch topics related to a specific subject using Datamuse API."""
    url = "https://api.datamuse.com/words"
    params = {
        "ml": seed,
        "max": limit
    }
    response = _api_get(url, params)
    if response is None:
        print("Error fetching related topics from Datamuse: request did not get through.")
        return set()
    try:
        return {item["word"] for item in response.json()}
    except Exception as e:
        print(f"Error fetching related topics from Datamuse: {e}")
        return set()

# _________________________________________________________________________________
# _________________________________________________________________________________

def promptFindingReference(is_dumped = True, file="PROMPT.txt") -> Optional[dict]:
    """Reads in a prompt from a text file, cleans the text, and stores the cleaned
    prompt in a JSON file. The prompt is cleaned by removing punctuation, converting
    to lowercase, tokenizing, removing stop words, removing words with repeated
    characters, and stemming. If the cleaned prompt is empty, a message is printed
    and the function returns early. Otherwise, the cleaned prompt is stored in the
    buffer.json file."""
    # Read in from prompt.txt
    with open(file, "r", encoding="utf-8", errors="ignore") as f:
        prompt = f.readlines()

    prompt = " ".join(prompt)

    # Clean the prompt text
    cleaned_prompt = clean_text(prompt)

    # Check if cleaned prompt is empty
    if not cleaned_prompt:
        print("No valid words found in the prompt.")

    if is_dumped:
        # Dump the cleaned prompt to the buffer.json file
        with open(buffer_json_path, "w") as f:
            dump(cleaned_prompt, f, ensure_ascii=False, indent=4)
        return None
    # else return the cleaned prompt as a dictionary 
    return cleaned_prompt

def permutate_topics() -> set[str]:
    """
    Reads a CSV of 'not found' topics (one per line), extracts unique words,
    and generates new topic strings by permuting those words into phrases.

    Args:
        max_words: Maximum number of words per generated topic (1 or 2 recommended).

    Returns:
        Set of newly generated topic strings.
    """
    # Step 1: collect all tokens from the file
    tokens = set()
    csv_path = Path(not_found_topics_csv)
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    # Split on whitespace; keep all parts
                    for word in line.split():
                        tokens.add(word)
    else:
        # If file doesn't exist, return empty set (or raise warning)
        return set()

    # Step 2: generate new topics from tokens
    tokens = tokens - stop_words  # Remove stop words from tokens
    new_topics = set()

    # Single‑word topics
    new_topics.update(tokens)

    # Two‑word ordered permutations (w1 w2) where w1 != w2
    for w1, w2 in permutations(tokens, 2):
        new_topics.add(f"{w1} {w2}")

    return new_topics


def deduplicate_topic_files():
    """Deduplicate identical files in the wiki_topics folder.

    Keeps the shortest file name for each unique piece of content and removes
    the rest. Duplicate topic names are appended to the not_found_topics file so
    they will be skipped in future processing.
    """
    file_groups = {}

    for topic_file in WIKI_FOLDER.glob("*.txt"):
        try:
            raw_text = topic_file.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            print(f"Unable to read {topic_file}: {exc}")
            continue

        normalized_text = re.sub(r"\s+", " ", raw_text).strip()
        content_hash = hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()
        file_groups.setdefault(content_hash, []).append(topic_file)

    duplicate_topics = []
    for files in file_groups.values():
        if len(files) <= 1:
            continue

        files.sort(key=lambda p: (len(p.name), p.name.lower()))
        keeper = files[0]
        duplicates = files[1:]

        for duplicate in duplicates:
            duplicate_topic = duplicate.stem.replace("_", " ")
            duplicate_topics.append(duplicate_topic)
            try:
                duplicate.unlink()
            except OSError as exc:
                print(f"Failed to remove duplicate file {duplicate.name}: {exc}")

    if duplicate_topics:
        with open(not_found_topics_csv, "a", encoding="utf-8") as f:
            for topic in sorted(set(duplicate_topics)):
                f.write(topic + "\n")
        print(f"Appended {len(set(duplicate_topics))} duplicate topics to {not_found_topics_csv}")


def tokenize_topics(TOPIC_LIST: set[str], max_workers: int = 2, wait_time: float = 0.5):
    """
    Tokenize topics and fetch Wikipedia articles in parallel.

    Args:
        TOPIC_LIST: Set of topic strings to fetch and tokenize
        max_workers: Number of concurrent threads for fetching (default: 2)
        wait_time: Minimum seconds between requests, across all threads (default: 0.5)
    """
    WIKI_FOLDER.mkdir(exist_ok=True)
    # Retrieve the "not found" topics from the CSV file
    not_found_topics = set()
    if Path(not_found_topics_csv).exists():
        with open(not_found_topics_csv, "r", encoding="utf-8") as f:
            for line in f:
                not_found_topics.add(line.strip())
    
    TOPIC_LIST = set(TOPIC_LIST) - not_found_topics
    del not_found_topics  # Free memory

    # Filter topics that don't need fetching
    topics_to_fetch = [
        topic for topic in TOPIC_LIST
        if topic and not (WIKI_FOLDER / (clean_filename(topic.replace(" ", "_").lower()) + ".txt")).exists()
    ]
    
    if not topics_to_fetch:
        print("All topics already exist. Skipping fetch phase.")
    else:
        print(f"Fetching {len(topics_to_fetch)} topics using {max_workers} concurrent workers...")
        _fetch_topics_parallel(topics_to_fetch, max_workers, wait_time)
    
    # STEP 2: Open DB and process tokens
    print("Processing topics and storing tokens in the database...")
    conn = sqlite3.connect(chunk_database_path)
    setup_database(conn, reset=False)
    cursor = conn.cursor()

    # Deduplicate wiki topic files with identical content.
    # Keep the shortest filename and record duplicate topics as not found.
    deduplicate_topic_files()
    remove_below_2KB_files = [f for f in WIKI_FOLDER.glob("*.txt") if f.stat().st_size < 2048]
    for f in remove_below_2KB_files:
        topic_name = f.stem.replace("_", " ")
        with open(not_found_topics_csv, "a", encoding="utf-8") as nf:
            nf.write(topic_name + "\n")
        try:
            f.unlink()
        except OSError as exc:
            print(f"Failed to remove small file {f.name}: {exc}")
    

    with open('topics.txt', 'w') as f:
        topics = (file.replace('_', ' ').removesuffix('.txt') for file in os.listdir('wiki_topics') if file.endswith('.txt'))
        f.write('\n'.join(topics))

    processed_tags = {
        row[0] for row in
        cursor.execute("SELECT DISTINCT topic FROM topic_token").fetchall()
    }

    topic_files = list(WIKI_FOLDER.glob("*.txt"))

    for topic_file in topic_files:
        tag_name = topic_file.stem
        if tag_name in processed_tags:
            continue
        print(f"Processing topic: {tag_name}")

        with open(topic_file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        result = clean_text(content)

        if not result:
            print(f"No valid tokens found for topic: {tag_name}")
            continue

        distance = sum(freq ** 2 for freq in result.values())
        
        if distance > 0:
            relation = [(token, freq, freq / distance) for token, freq in result.items()]
        else:
            relation = []

        # Insert tokens into the database
        for token, freq, rel in relation:
            cursor.execute(
                "INSERT OR IGNORE INTO topic_token (topic, token, frequency, relational_distance) VALUES (?, ?, ?, ?)",
                (tag_name, token, freq, rel)
            )

    conn.commit()
    conn.close()
    print("\nPipeline completed successfully.")


def _fetch_topics_parallel(topics_list: list, max_workers: int = 2, wait_time: float = 0.5):
    """
    Fetch multiple Wikipedia articles, spacing requests globally so the API does
    not throttle us.

    Only topics Wikipedia positively reports as missing are written to
    not_found_topics.txt. Topics that merely failed to download (429, timeout,
    connection reset) are left out of that file so a later run retries them --
    treating those as "missing" is what silently shrank the topic set before.

    Args:
        topics_list: List of topic titles to fetch
        max_workers: Number of concurrent threads (default: 2)
        wait_time: Minimum seconds between requests, across all threads (default: 0.5)
    """
    lock = Lock()
    size = len(topics_list)
    set_request_interval(wait_time)

    def fetch_one(topic: str) -> tuple:
        filename = clean_filename(topic.replace(" ", "_").lower()) + ".txt"
        file_path = WIKI_FOLDER / filename

        try:
            content, status = fetch_article(topic)
        except Exception as e:
            # Unexpected local failure: report it, but never blacklist on it.
            print(f"[ERROR] {topic}: {e}")
            return topic, FETCH_UNAVAILABLE

        if status == FETCH_MISSING or (status == FETCH_OK and not content):
            # Confirmed absent (or present but empty) -- safe to skip in future runs.
            with lock:
                with open(not_found_topics_csv, "a", encoding="utf-8") as f:
                    f.write(topic + "\n")
            return topic, FETCH_MISSING

        if status != FETCH_OK:
            return topic, FETCH_UNAVAILABLE

        file_path.write_text(content, encoding="utf-8")
        return topic, FETCH_OK

    completed = fetched = missing = unavailable = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, topic): topic for topic in topics_list}

        for future in as_completed(futures):
            topic, status = future.result()
            completed += 1

            if status == FETCH_OK:
                fetched += 1
                print(f"Fetched ({completed}/{size}): {topic}")
            elif status == FETCH_MISSING:
                missing += 1
            else:
                unavailable += 1

    print(f"\nFetch summary: {fetched} fetched, {missing} missing (blacklisted), "
          f"{unavailable} unavailable (will be retried on the next run).")
    if unavailable:
        print("Re-run --topicTokenize later to pick up the unavailable topics.")
