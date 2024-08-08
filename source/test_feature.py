import sqlite3
import modules.path as path

def featch_all_rows_to_found_limit(limit = 100) -> None:
    cursor.execute("SELECT * FROM word_frequencies Order BY frequency DESC LIMIT ?", (limit, ))
    for row in cursor.fetchall():
        print(row, end=", ")

def get_the_coverage(counting_frequency = 0, sum_frequency = 100, batch_size = 100, threshold = 0.80, offset = 0) -> tuple[int, int]:
    """
    Description:
        This function is used to get the coverage of the word frequencies in the database to the nearest limit

    Args:
        counting_frequency (int, optional): The current counting frequency. Defaults to 0.
        sum_frequency (int, optional): The total sum of frequency. Defaults to 100.
        batch_size (int, optional): The size of the batch. Defaults to 100.
        threshold (float, optional): The threshold for the coverage. Defaults to 0.80.
        offset (int, optional): The offset for the batch. Defaults to 0.

    Returns:
        tuple: The updated counting frequency and the updated offset
    """

    coverage = counting_frequency / sum_frequency
    print("-----------------------------")

    while coverage < threshold:
        cursor.execute("SELECT SUM(frequency) FROM (SELECT frequency FROM word_frequencies ORDER BY frequency DESC LIMIT ? OFFSET ?)", (batch_size, offset))
        batch_sum = cursor.fetchone()[0]
        
        if batch_sum is None:  # In case there are no more rows to fetch
            break
        
        counting_frequency += batch_sum
        offset += batch_size

        current_coverage = counting_frequency / sum_frequency
        coverage_gain = current_coverage - coverage
        coverage = current_coverage

        # Prevent division by zero in case coverage_gain is zero
        if coverage_gain != 0:
            marginal_gain = batch_sum / (coverage_gain * 100)
        else:
            marginal_gain = float('inf')  # or some other appropriate value

        print(f"Counting frequency: {counting_frequency}")
        print(f"Coverage: {coverage:.2%}")
        print(f"Frequency gain: {batch_sum}")
        print(f"Coverage gain: {coverage_gain:.2%}")
        print("-----------------------------")

    return counting_frequency, offset

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

# Parameters
counting_frequency = 0
batch_size = 100
threshold = 0.82
offset = 0

counting_frequency, offset = get_the_coverage(counting_frequency, sum_frequency, batch_size, threshold, offset)
# featch_all_rows_to_found_limit(batch_size + offset)

conn.close()