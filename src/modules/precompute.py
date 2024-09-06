# def precompute_title_vector(database_path: str) -> None:
#     conn = sqlite3.connect(database_path)
#     cursor = conn.cursor()

#     def create_tables(title_ids: list) -> None:
#         cursor.execute("DROP TABLE IF EXISTS title_analysis")
#         cursor.execute("DROP TABLE IF EXISTS title_normalized")
#         # Create command strings for columns
#         columns_INT = ', '.join([f"T_{title_id} INTEGER DEFAULT 0" for title_id in title_ids])
#         columns_REAL = ', '.join([f"T_{title_id} REAL DEFAULT 0.0" for title_id in title_ids])
        
#         # Create the tables with the necessary columns
#         cursor.execute(f"""
#             CREATE TABLE title_analysis (
#                 word TEXT PRIMARY KEY, 
#                 {columns_INT},
#                 FOREIGN KEY(word) REFERENCES coverage_analysis(word)
#             )
#         """)
#         cursor.execute(f"""
#             CREATE TABLE title_normalized (
#                 word TEXT PRIMARY KEY,
#                 {columns_REAL},
#                 FOREIGN KEY(word) REFERENCES coverage_analysis(word)
#             )
#         """)

#         # Insert words into tables
#         cursor.execute("INSERT INTO title_analysis (word) SELECT DISTINCT word FROM coverage_analysis")
#         cursor.execute("INSERT INTO title_normalized (word) SELECT DISTINCT word FROM coverage_analysis")

#     def process_title_analysis(title_ids: list[str], words: list[str], cursor: sqlite3.Cursor) -> None:
#         for title in title_ids:
#             token_list = retrieve_token_list(title_id=title, cursor=cursor)
#             word_counts = {word: token_list.count(word) for word in words if word in token_list}

#             # Batch update the title_analysis table
#             update_data = [(count, word) for word, count in word_counts.items()]
#             cursor.executemany(
#                 f"UPDATE title_analysis SET T_{title} = ? WHERE word = ?",
#                 update_data
#             )
#         conn.commit()

#     def normalize_vector(title_ids: list[str]) -> None:
#         for title in title_ids:
#             length = cursor.execute(f"SELECT SUM(T_{title} * T_{title}) FROM title_analysis").fetchone()[0]
#             length = sqrt(length)
#             cursor.execute(f"""
#                 UPDATE title_normalized
#                     SET T_{title} = 
#                         (SELECT T_{title} FROM title_analysis WHERE title_normalized.word = title_analysis.word) /(1 + {length})""")
#             conn.commit()

#     def get_words() -> list[str]:
#         cursor.execute("SELECT word FROM coverage_analysis")
#         return [word[0] for word in cursor.fetchall()]

#     # Main flow

#     title_ids = get_title_ids(cursor=cursor)
#     words = get_words()
    
#     print_and_log("Creating tables...")
#     create_tables(title_ids=title_ids)
#     print_and_log("Finished creating tables.")
    
#     print_and_log("Processing title analysis...")
#     process_title_analysis(title_ids=title_ids, words=words, cursor=cursor)
#     print_and_log("Finished processing title analysis.")
    
#     print_and_log("Normalizing vectors...")
#     normalize_vector(title_ids=title_ids)
#     print_and_log("Finished normalizing vectors.")

#     conn.commit()
#     conn.close()

# def suggest_top_titles(database_path: str, prompt: str, top_n = 10):
#     conn = sqlite3.connect(database_path)
#     cursor = conn.cursor()

#     prompt = clean_text(prompt)

#     cursor.execute("SELECT word FROM coverage_analysis")
#     words = cursor.fetchall()
#     words = {word[0]: 0 for word in words}

#     for token in words.keys():
#         words[token] = prompt.count(token)

#     length_prompt = sqrt(sum([value * value for value in words.values()]))

#     normalized_prompt = {key: value / length_prompt for key, value in words.items()}

#     title_list = cursor.execute("SELECT id FROM file_list WHERE file_type = 'pdf' AND chunk_count > 0").fetchall()
#     # create an array of zeros
#     title_list = {name[0]: 0 for name in title_list}

#     # get non-zero keys
#     key_list = [key for key, value in normalized_prompt.items() if value != 0]

#     # get values
#     for title in title_list.keys():
#         for key in key_list:
#             cursor.execute(f"SELECT T_{title} FROM title_normalized WHERE word = ?", (key,))
#             title_list[title] += cursor.fetchone()[0] * normalized_prompt[key]

#     top_10 = sorted(title_list.items(), key=lambda x: x[1], reverse=True)[:top_n]

#     # Look up the name of the top 10 titles
#     for title, score in top_10:
#         cursor.execute("SELECT file_name FROM file_list WHERE id = ?", (title,))
#         print(f"{score:.18f}: {title} - {cursor.fetchone()[0]}")

#     conn.close()