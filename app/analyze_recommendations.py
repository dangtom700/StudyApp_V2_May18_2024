"""
Recommendation Analyzer
Analyze and configure the item_matrix table for recommendations
Run from parent directory of app folder
"""

import sqlite3
import sys
from pathlib import Path

# Add app/src to path
sys.path.insert(0, str(Path(__file__).parent / "app" / "src"))
from modules.path import chunk_database_path


class RecommendationAnalyzer:
    """Analyze recommendation data"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

    def check_item_matrix(self):
        """Check if item_matrix table exists and show structure"""
        print("\n" + "=" * 70)
        print("ITEM_MATRIX TABLE ANALYSIS")
        print("=" * 70)

        # Check if table exists
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='item_matrix'
        """)

        if not self.cursor.fetchone():
            print("✗ item_matrix table NOT FOUND\n")
            self.suggest_create_item_matrix()
            return False

        print("✓ item_matrix table found\n")

        # Show schema
        self.cursor.execute("PRAGMA table_info(item_matrix)")
        columns = self.cursor.fetchall()

        print("Columns:")
        for col in columns:
            print(f"  • {col[1]:20} ({col[2]})")

        # Show row count
        self.cursor.execute("SELECT COUNT(*) FROM item_matrix")
        count = self.cursor.fetchone()[0]
        print(f"\nTotal rows: {count}")

        # Show sample rows
        if count > 0:
            self.cursor.execute("SELECT * FROM item_matrix LIMIT 3")
            rows = self.cursor.fetchall()
            print("\nSample rows:")
            for row in rows:
                print(f"  {row}")

        return True

    def suggest_create_item_matrix(self):
        """Suggest how to create item_matrix from TF-IDF"""
        print("SUGGESTION: How to create item_matrix\n")
        print("If you have TF-IDF vectors computed, you can create item_matrix like this:\n")

        sql_example = """
-- Option 1: If you have tfidf vectors table
CREATE TABLE IF NOT EXISTS item_matrix AS
SELECT
    f1.file_name as file_name1,
    f2.file_name as file_name2,
    SQRT(SUM(POWER(v1.weight - v2.weight, 2))) as distance
FROM tfidf_vectors v1
JOIN tfidf_vectors v2 ON v1.token_id = v2.token_id
JOIN chunks f1 ON v1.chunk_id = f1.chunk_id
JOIN chunks f2 ON v2.chunk_id = f2.chunk_id
WHERE f1.file_name < f2.file_name
GROUP BY f1.file_name, f2.file_name;

-- Option 2: Create from tokens (if available)
CREATE TABLE IF NOT EXISTS item_matrix (
    file_name1 TEXT,
    file_name2 TEXT,
    distance REAL,
    PRIMARY KEY (file_name1, file_name2)
);

-- Then populate with your similarity calculations
        """
        print(sql_example)

        print("\nAlternatively, run the Python extraction scripts:")
        print("  cd app/src && python main.py --computeTFIDF")
        print("  cd app/src && python main.py --topicTokenize")

    def analyze_chunks(self):
        """Analyze chunks table"""
        print("\n" + "=" * 70)
        print("CHUNKS TABLE ANALYSIS")
        print("=" * 70)

        # Count unique files
        self.cursor.execute("SELECT COUNT(DISTINCT file_name) FROM chunks")
        unique_files = self.cursor.fetchone()[0]
        print(f"✓ Unique PDF files: {unique_files}")

        # Get file list
        self.cursor.execute("""
            SELECT file_name, COUNT(*) as chunk_count
            FROM chunks
            GROUP BY file_name
            ORDER BY chunk_count DESC
        """)

        print("\nTop files by chunk count:")
        for i, row in enumerate(self.cursor.fetchall(), 1):
            if i > 10:
                break
            print(f"  {i:2}. {row[0]:30} ({row[1]:5} chunks)")

    def check_tfidf(self):
        """Check if TF-IDF data exists"""
        print("\n" + "=" * 70)
        print("TF-IDF TABLE CHECK")
        print("=" * 70)

        # Look for common TF-IDF table names
        tfidf_tables = ['tfidf_vectors', 'tfidf', 'tf_idf', 'vectors']

        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)
        existing_tables = {row[0] for row in self.cursor.fetchall()}

        found_tfidf = False
        for tfidf_name in tfidf_tables:
            if tfidf_name in existing_tables:
                print(f"✓ Found TF-IDF table: {tfidf_name}")

                # Get count
                self.cursor.execute(f"SELECT COUNT(*) FROM {tfidf_name}")
                count = self.cursor.fetchone()[0]
                print(f"  Rows: {count}\n")

                found_tfidf = True

        if not found_tfidf:
            print("✗ No TF-IDF table found")
            print("  To compute TF-IDF, run:")
            print("    cd app/src && python main.py --computeTFIDF\n")

    def get_recommendation_query(self):
        """Show the actual query used for recommendations"""
        print("\n" + "=" * 70)
        print("ACTIVE RECOMMENDATION QUERY")
        print("=" * 70)

        query = """
SELECT
    CASE
        WHEN file_name1 = ? THEN file_name2
        ELSE file_name1
    END as other_file,
    distance
FROM item_matrix
WHERE file_name1 = ? OR file_name2 = ?
ORDER BY distance DESC
LIMIT ?
        """
        print("\nThe app uses this query:")
        print(query)

        print("\nIf item_matrix doesn't exist, it falls back to random files.")
        print("To get real recommendations, ensure item_matrix is populated!")


def main():
    analyzer = RecommendationAnalyzer(chunk_database_path)

    try:
        analyzer.check_item_matrix()
        analyzer.analyze_chunks()
        analyzer.check_tfidf()
        analyzer.get_recommendation_query()

        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("""
1. If item_matrix exists → Recommendations will work! ✓
2. If item_matrix is missing:
   a. Run: cd app/src && python main.py --computeTFIDF
   b. Then create item_matrix from TF-IDF vectors
   c. Or populate it with your own similarity calculations
3. Check app/APP_GUIDE.md for more details
        """)

    finally:
        analyzer.close()


if __name__ == "__main__":
    main()