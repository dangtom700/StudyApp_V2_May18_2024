import sqlite3

conn = sqlite3.connect('data/chunks.db')
cursor = conn.cursor()

actual_sum_freq = cursor.execute("SELECT SUM(frequency) FROM word_frequencies").fetchone()[0]
for i in range(0, 150, 10):
    print(f"i: {i}")

    total_frequency = cursor.execute(f"SELECT SUM(frequency) FROM word_frequencies WHERE frequency > {i}").fetchone()[0]
    print(f"Total frequency: {total_frequency}")

    num_words = cursor.execute(f"SELECT COUNT(*) FROM word_frequencies WHERE frequency > {i}").fetchone()[0]
    print(f"Number of words: {num_words}")

    # 20/80
    factor = 0.30
    top_percent = round(num_words * factor)
    print(f"Top {factor * 100}%: {top_percent}")
    # Order in decending order
    cursor.execute("SELECT * FROM word_frequencies ORDER BY frequency DESC")
    most_popular_percent = 0
    for _ in range(top_percent):
        most_popular_percent += cursor.fetchone()[1]

    print(f"Sum of top {factor * 100}%: {most_popular_percent}")

    popularity_top_percent = most_popular_percent / total_frequency * 100
    print(popularity_top_percent)

    print(f"Actual top {factor * 100}%: {most_popular_percent / actual_sum_freq * 100}")

conn.close()