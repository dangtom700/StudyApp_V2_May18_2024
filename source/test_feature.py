"""
data normalization and vector length computation
"""
import sqlite3
import modules.path as path
from modules.extract_pdf import clean_text
from math import sqrt

def suggest_top_titles(database_path: str, prompt: str, top_n = 10):
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    prompt = clean_text(prompt)

    cursor.execute("SELECT word FROM coverage_analysis")
    words = cursor.fetchall()
    words = {word[0]: 0 for word in words}

    for token in words.keys():
        words[token] = prompt.count(token)

    length_prompt = sqrt(sum([value * value for value in words.values()]))

    normalized_prompt = {key: value / length_prompt for key, value in words.items()}

    title_list = cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0").fetchall()
    # create an array of zeros
    title_list = {name[0]: 0 for name in title_list}

    # get non-zero keys
    key_list = [key for key, value in normalized_prompt.items() if value != 0]

    # get values
    for title in title_list.keys():
        for key in key_list:
            cursor.execute(f"SELECT title_{title} FROM title_normalized WHERE word = ?", (key,))
            title_list[title] += cursor.fetchone()[0] * normalized_prompt[key]

    top_10 = sorted(title_list.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # Look up the name of the top 10 titles
    for title, score in top_10:
        cursor.execute("SELECT file_name FROM file_list WHERE id = ?", (title,))
        print(f"{score:.18f}: {title} - {cursor.fetchone()[0]}")

    conn.close()

prompt = "AI has changed the traditional IoT networks, converted the services into more intelligent networks, and received tremendous interest from communities and industries. The amazing and attractive services of AI technology have resulted in the adoption of more advanced communication applications"

suggest_top_titles(database_path=path.chunk_database_path, prompt=prompt, top_n=3)