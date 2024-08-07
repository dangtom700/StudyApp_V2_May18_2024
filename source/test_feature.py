import sqlite3
import modules.path as path

conn = sqlite3.connect(path.chunk_database_path)
cursor = conn.cursor()

total_count = cursor.execute("SELECT COUNT(*) FROM word_frequencies").fetchone()[0]
print(f"Total number of words: {total_count}")

# count the number of word that has frequency from 1 to 10
for i in range(1, 11):
    cursor.execute(f"SELECT COUNT(*) FROM word_frequencies WHERE frequency = {i}")
    count = cursor.fetchone()[0]
    print(f"Number of word that has frequency of {i}: {count}")

# count the number of word that has frequency from 10 to 100 in steps of 10
for i in range(10, 101, 10):
    cursor.execute(f"SELECT COUNT(*) FROM word_frequencies WHERE frequency = {i}")
    count = cursor.fetchone()[0]
    print(f"Number of word that has frequency of {i}: {count}")

# count the number of word that has frequency from 100 to 1000 in steps of 100
for i in range(100, 1001, 100):
    cursor.execute(f"SELECT COUNT(*) FROM word_frequencies WHERE frequency = {i}")
    count = cursor.fetchone()[0]
    print(f"Number of word that has frequency of {i}: {count}")


conn.close()