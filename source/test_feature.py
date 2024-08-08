import sqlite3
import modules.path as path

conn = sqlite3.connect(path.chunk_database_path)
cursor = conn.cursor()

# Order the table in descending order
cursor.execute("SELECT * FROM word_frequencies ORDER BY frequency DESC")

# get the sum of frequency from the table
cursor.execute("SELECT SUM(frequency) FROM word_frequencies")
sum_frequency = cursor.fetchone()[0]
print(f"Sum of frequency: {sum_frequency}")

# get the average of frequency from the table
cursor.execute("SELECT AVG(frequency) FROM word_frequencies")
avg_frequency = cursor.fetchone()[0]
print(f"Average of frequency: {avg_frequency}")

counting_frequency = 0
batch_size = 100
threshold = 0.63
offset = 0


while round(counting_frequency / sum_frequency, 2) < threshold:
    cursor.execute("SELECT SUM(frequency) FROM (SELECT frequency FROM word_frequencies LIMIT ? OFFSET ?)", (batch_size, offset))
    batch_sum = cursor.fetchone()[0]
    
    if batch_sum is None:  # In case there are no more rows to fetch
        break
    
    counting_frequency += batch_sum
    offset += batch_size
    
    print(f"Counting frequency: {counting_frequency}")
    print(f"Coverage: {counting_frequency / sum_frequency:.2%}")


conn.close()