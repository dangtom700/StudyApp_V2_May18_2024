import sqlite3
import data.path as path

def getBasicAnalytics(cursor) -> None:
    # sort the frequency in ascending order
    cursor.execute("SELECT word, frequency FROM word_frequencies ORDER BY frequency ASC")
    # get the min frequency
    cursor.execute("SELECT MIN(frequency) FROM word_frequencies")
    min_frequency = cursor.fetchone()[0]
    print(f"Minimum frequency: {min_frequency}")
    # get the max frequency
    cursor.execute("SELECT MAX(frequency) FROM word_frequencies")
    max_frequency = cursor.fetchone()[0]
    print(f"Maximum frequency: {max_frequency}")
    # get total number of rows
    cursor.execute("SELECT COUNT(*) FROM word_frequencies")
    total_rows = cursor.fetchone()[0]
    print(f"Total number of rows: {total_rows}")

def TestFrequencyBounds(lower_limit: int, upper_limit: int, cursor) -> None:
    # count frequency of each frequency set
    offset = 500
    chunk_count = 1
    total_words = 0
    
    while True:
        lower_bound = lower_limit + (chunk_count-1) * offset
        upper_bound = min(lower_limit + chunk_count * offset, upper_limit)
        cursor.execute(
            "SELECT COUNT(*) FROM word_frequencies WHERE frequency >= ? AND frequency < ?",
            (lower_bound, upper_bound),
        )
        frequency_count = cursor.fetchone()[0]
        total_words += frequency_count
        print(f"Frequency count between {lower_bound} and {upper_bound} of chunk {chunk_count}: {frequency_count}")
        chunk_count += 1
        if lower_bound >= upper_limit or upper_bound >= upper_limit:
            break
        cursor.execute("SELECT word FROM word_frequencies WHERE frequency >= ? AND frequency < ?", (lower_bound, upper_bound))
        words = cursor.fetchall()
        words = [word[0] for word in words if len(word[0]) > 4]
        print(words)
    print(f"Total words: {total_words}")

conn = sqlite3.connect(path.chunk_database_path)
cursor = conn.cursor()
getBasicAnalytics(cursor)
TestFrequencyBounds(1, 20000, cursor)
TestFrequencyBounds(1, 3000, cursor)
TestFrequencyBounds(2000, 15000, cursor)
TestFrequencyBounds(4000, 9000, cursor)
conn.close()