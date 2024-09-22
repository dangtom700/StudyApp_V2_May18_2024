import sqlite3
import modules.path as path

def getWordFrequencyAnalysis(BATCH_SIZE=1000, threshold=0.96) -> int:
    # Connect to the database
    conn = sqlite3.connect(path.chunk_database_path)
    cursor = conn.cursor()

    # Get the total sum of frequencies
    total_frequency = cursor.execute("SELECT SUM(frequency) FROM word_frequencies").fetchone()[0]
    print(f"Total frequency: {total_frequency}")

    # Initialize batch processing variables
    inserted_sum = 0
    offset = 0

    # Threshold limit based on the total frequency
    threshold_value = total_frequency * threshold

    # Create the coverage_analysis table
    cursor.execute("DROP TABLE IF EXISTS coverage_analysis")
    cursor.execute("""
        CREATE TABLE coverage_analysis (
            word TEXT PRIMARY KEY, 
            frequency INTEGER,
            FOREIGN KEY (word, frequency) REFERENCES word_frequencies(word, frequency)
        )
    """)

    # Loop to insert rows in batches of 1000 and check the cumulative frequency
    while inserted_sum < threshold_value:
        # Select the next batch of 1000 rows
        rows = cursor.execute("""
            SELECT word, frequency FROM word_frequencies 
            ORDER BY frequency DESC 
            LIMIT ? OFFSET ?
        """, (BATCH_SIZE, offset)).fetchall()

        if not rows:
            # If no more rows are available, break the loop
            break

        # Insert the current batch into the coverage_analysis table
        cursor.executemany("""
            INSERT INTO coverage_analysis (word, frequency) 
            VALUES (?, ?)
        """, rows)

        # Update the sum of the inserted frequencies
        batch_sum = sum(row[1] for row in rows)
        inserted_sum += batch_sum
        print(f"Inserted batch sum: {batch_sum}, Total inserted sum: {inserted_sum}")

        # Move the offset for the next batch
        offset += BATCH_SIZE

    # Get the number of rows inserted into the coverage_analysis table
    rows_inserted = cursor.execute("SELECT COUNT(*) FROM coverage_analysis").fetchone()[0]

    # Complete transaction and close the connection
    conn.commit()
    conn.close()

    return rows_inserted
