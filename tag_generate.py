import sqlite3
import subprocess
import requests
import re
from pathlib import Path
import time

# ------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------

WIKI_FOLDER = Path("wiki_topics")
PROMPT_FILE = Path("Prompt.txt")
OUTPUT_FILE = Path("outputPrompt.txt")
EXECUTABLE_PATH = Path("config") / "main.bat"
DB_PATH = "tags.db"

API_URL = "https://en.wikipedia.org/w/api.php"
DISTANCE_THRESHOLD = 0.4

HEADERS = {
    "User-Agent": "TopicDatasetBuilder/1.0 (GodKnows@example.com)"
}

TOPIC_LIST = ()

# ------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------

def setup_database(conn):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            Name TEXT,
            ID TEXT,
            Distance REAL,
            Tag TEXT,
            PRIMARY KEY (ID, Tag)
        )
    """)
    conn.commit()


# ------------------------------------------------------------
# WIKIPEDIA FETCH
# ------------------------------------------------------------

def clean_filename(name):
    return re.sub(r'[^\w\-_\. ]', '_', name)

def fetch_article(title):
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,
        "redirects": 1
    }

    try:
        response = requests.get(API_URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Wiki request failed for {title}: {e}")
        return None

    pages = data.get("query", {}).get("pages", {})
    page = next(iter(pages.values()))

    if "missing" in page:
        return None

    return page.get("extract", "")

# ------------------------------------------------------------
# GENERATOR EXECUTION
# ------------------------------------------------------------

def run_generator():
    try:
        result = subprocess.run(
            [str(EXECUTABLE_PATH)],
            check=True,
            capture_output=True,
            text=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print("Generator failed.")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def parse_output(tag_name):

    if not OUTPUT_FILE.exists():
        print("outputPrompt.txt missing.")
        return []

    content = OUTPUT_FILE.read_text(encoding="utf-8")

    lines = content.splitlines()[2:]  # ignore first 2 lines
    content = "\n".join(lines)

    blocks = content.split("-----------------------------------------------------------------")

    entries = []

    for block in blocks:

        id_match = re.search(r"ID:\s*([a-f0-9]+)", block)
        distance_match = re.search(r"Distance:\s*([0-9.]+)", block)
        name_match = re.search(r"\[\[(.*?)\]\]", block)

        if not (id_match and distance_match and name_match):
            continue

        book_id = id_match.group(1)
        distance = float(distance_match.group(1))
        name = name_match.group(1).strip()

        if distance > DISTANCE_THRESHOLD:
            entries.append((name, book_id, distance, tag_name))

    return entries

if __name__ == "__main__":
    WIKI_FOLDER.mkdir(exist_ok=True)

    # STEP 1: Fetch missing wiki topics
    for topic in TOPIC_LIST:
        name_topic = topic.replace(" ", "_").lower()
        file_path = WIKI_FOLDER / f"{clean_filename(name_topic)}.txt"

        if file_path.exists():
            continue

        # print(f"Fetching Wiki article: {topic}")
        content = fetch_article(topic)

        if not content:
            print(f"Wiki article not found: {topic}")
            continue

        file_path.write_text(content, encoding="utf-8")
        time.sleep(1)

    # STEP 2: Open DB
    conn = sqlite3.connect(DB_PATH)
    setup_database(conn)
    cursor = conn.cursor()

    processed_tags = {
        row[0] for row in
        cursor.execute("SELECT DISTINCT Tag FROM tags").fetchall()
    }

    topic_files = list(WIKI_FOLDER.glob("*.txt"))

    for topic_file in topic_files:

        tag_name = topic_file.stem

        if tag_name in processed_tags:
            continue

        print(f"\nProcessing topic: {tag_name}")

        # Write prompt
        PROMPT_FILE.write_text(
            topic_file.read_text(encoding="utf-8"),
            encoding="utf-8"
        )

        # Run generator
        if not run_generator():
            print("Skipping due to generator failure.")
            continue

        time.sleep(0.5)

        # Parse output
        entries = parse_output(tag_name)

        # Insert into DB
        for entry in entries:
            cursor.execute("""
                INSERT OR IGNORE INTO tags (Name, ID, Distance, Tag)
                VALUES (?, ?, ?, ?)
            """, entry)

        conn.commit()
        print(f"Inserted {len(entries)} tags.")

    conn.close()
    print("\nPipeline completed successfully.")
