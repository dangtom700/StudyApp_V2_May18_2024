"""
Database Inspector Utility
Inspect and verify the pdf_text.db database structure and content
Run from parent directory of app folder
"""

import sqlite3
import sys
from tabulate import tabulate
from pathlib import Path
import os

# Add app/src to path
sys.path.insert(0, str(Path(__file__).parent / "app" / "src"))

chunk_database_path = os.getcwd() + "\\" + "data\\pdf_text.db"

class DatabaseInspector:
    """Inspect database structure and content"""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()

    def connect(self):
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            print(f"✓ Connected to {self.db_path}\n")
        except sqlite3.Error as e:
            print(f"✗ Connection failed: {e}")
            sys.exit(1)

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def show_tables(self):
        """List all tables"""
        print("=" * 60)
        print("DATABASE TABLES")
        print("=" * 60)

        self.cursor.execute("""
            SELECT name, type FROM sqlite_master
            WHERE type IN ('table', 'index')
            ORDER BY type, name
        """)

        tables = []
        for row in self.cursor.fetchall():
            tables.append([row[0], row[1]])

        if tables:
            print(tabulate(tables, headers=["Name", "Type"], tablefmt="grid"))
        else:
            print("No tables found")
        print()

    def show_table_schema(self, table_name):
        """Show schema for a specific table"""
        print(f"\nTable: {table_name}")
        print("-" * 60)

        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns = self.cursor.fetchall()

            if not columns:
                print(f"Table '{table_name}' not found")
                return

            col_data = []
            for col in columns:
                col_data.append([
                    col[1],  # name
                    col[2],  # type
                    "NOT NULL" if col[3] else "NULL",
                    col[4] if col[4] else "-",  # default
                    "PK" if col[5] else "-"  # primary key
                ])

            print(tabulate(col_data,
                          headers=["Column", "Type", "Nullable", "Default", "PK"],
                          tablefmt="grid"))
        except sqlite3.Error as e:
            print(f"Error: {e}")
        print()

    def show_all_schemas(self):
        """Show schemas for all tables"""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)

        tables = [row[0] for row in self.cursor.fetchall()]

        for table in tables:
            self.show_table_schema(table)

    def show_table_stats(self, table_name):
        """Show row count and sample data"""
        try:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = self.cursor.fetchone()[0]

            print(f"\nTable: {table_name}")
            print(f"Total Rows: {count}")

            if count > 0:
                # Get column names
                self.cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [col[1] for col in self.cursor.fetchall()]

                # Show first 5 rows
                self.cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                rows = self.cursor.fetchall()

                print("\nFirst 5 rows:")
                print(tabulate(rows, headers=columns, tablefmt="grid", maxcolwidths=30))
        except sqlite3.Error as e:
            print(f"Error: {e}")
        print()

    def show_all_stats(self):
        """Show stats for all tables"""
        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)

        tables = [row[0] for row in self.cursor.fetchall()]

        print("\n" + "=" * 60)
        print("TABLE STATISTICS")
        print("=" * 60)

        stats = []
        for table in tables:
            try:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = self.cursor.fetchone()[0]
                stats.append([table, count])
            except sqlite3.Error:
                stats.append([table, "Error"])

        print(tabulate(stats, headers=["Table", "Row Count"], tablefmt="grid"))
        print()

    def check_requirements(self):
        """Check if database has required tables for the app"""
        print("=" * 60)
        print("REQUIREMENT CHECK")
        print("=" * 60)

        required_tables = ['chunks']
        optional_tables = ['item_matrix', 'tokens', 'word_frequency']

        self.cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)
        existing_tables = {row[0] for row in self.cursor.fetchall()}

        print("\nRequired Tables:")
        for table in required_tables:
            status = "✓" if table in existing_tables else "✗"
            print(f"  {status} {table}")

        print("\nOptional Tables (for full features):")
        for table in optional_tables:
            status = "✓" if table in existing_tables else "•"
            print(f"  {status} {table}")

        print()

        # Check chunks table structure
        if 'chunks' in existing_tables:
            self.cursor.execute("PRAGMA table_info(chunks)")
            columns = {col[1] for col in self.cursor.fetchall()}

            required_cols = ['file_name', 'text_content', 'chunk_id']
            print("\nChunks Table Structure:")
            for col in required_cols:
                status = "✓" if col in columns else "✗"
                print(f"  {status} {col}")

        print()


def main():
    """Main menu"""
    inspector = DatabaseInspector(chunk_database_path)

    while True:
        print("\n" + "=" * 60)
        print("DATABASE INSPECTOR")
        print("=" * 60)
        print("1. Show all tables")
        print("2. Show complete schema for all tables")
        print("3. Show table statistics")
        print("4. Show full table details")
        print("5. Check app requirements")
        print("6. Exit")
        print()

        choice = input("Select option (1-6): ").strip()

        if choice == "1":
            inspector.show_tables()

        elif choice == "2":
            inspector.show_all_schemas()

        elif choice == "3":
            inspector.show_all_stats()

        elif choice == "4":
            inspector.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in inspector.cursor.fetchall()]

            if not tables:
                print("No tables found")
                continue

            print("\nAvailable tables:")
            for i, table in enumerate(tables, 1):
                print(f"  {i}. {table}")

            table_choice = input("Select table number: ").strip()
            try:
                table_idx = int(table_choice) - 1
                if 0 <= table_idx < len(tables):
                    inspector.show_table_stats(tables[table_idx])
                else:
                    print("Invalid selection")
            except ValueError:
                print("Invalid input")

        elif choice == "5":
            inspector.check_requirements()

        elif choice == "6":
            print("Goodbye!")
            break

        else:
            print("Invalid option")

    inspector.close()


if __name__ == "__main__":
    main()