"""
Database Manager for Study App
Handles all database operations for PDF lookup, search, and recommendations
"""

import sqlite3
from typing import List, Tuple, Optional
from pathlib import Path


class DatabaseManager:
    """Manages all database operations"""
    
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
            # Enable return of column names as keys
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def get_all_pdfs(self) -> List[str]:
        """Get list of all PDF files in database"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT file_name FROM file_info 
                ORDER BY file_name
            """)
            results = self.cursor.fetchall()
            return [row[0] for row in results]
        except sqlite3.Error as e:
            print(f"Error fetching PDFs: {e}")
            return []
    
    def get_pdf_info(self, file_name: str) -> Optional[Tuple[str, int]]:
        """Get PDF information: (file_path, chunk_count)"""
        try:
            self.cursor.execute("""
                SELECT file_path, chunk_count FROM file_info 
                WHERE file_name = ?
            """, (file_name,))
            
            result = self.cursor.fetchone()
            if result:
                return (result[0], result[1])
            return None
        except sqlite3.Error as e:
            print(f"Error fetching PDF info: {e}")
            return None
    
    def get_pdf_preview(self, file_name: str, chars: int = 500) -> Optional[str]:
        """Get first chunk preview of PDF"""
        try:
            self.cursor.execute("""
                SELECT chunk_text FROM pdf_chunks 
                WHERE file_name = ? 
                ORDER BY chunk_id 
                LIMIT 1
            """, (file_name+".txt",))
            
            result = self.cursor.fetchone()
            if result:
                text = result[0]
                return text[:chars] + "..." if text and len(text) > chars else text
            return None
        except sqlite3.Error as e:
            print(f"Error fetching preview: {e}")
            return None
    
    def search_files(self, keyword: str, max_results: int = 20) -> List[Tuple[str, str, int]]:
        """
        Search for files containing keyword
        Returns: [(file_name, chunk_text, chunk_id), ...]
        """
        try:
            # Search in text_content using LIKE for basic full-text search
            query = f"%{keyword}%"
            
            self.cursor.execute("""
                SELECT file_name, chunk_text, chunk_id 
                FROM pdf_chunks 
                WHERE chunk_text LIKE ? 
                ORDER BY file_name 
                LIMIT ?
            """, (query, max_results))
            
            results = self.cursor.fetchall()
            return [(row[0], row[1], row[2]) for row in results]
        except sqlite3.Error as e:
            print(f"Error searching files: {e}")
            return []
    
    def get_recommendations(self, file_name: str, count: int = 10) -> List[Tuple[str, float]]:
        """
        Get recommendations for a file based on comparison distances
        Returns files with greatest distance (most similar)
        Format: [(recommended_file_name, distance_score), ...]
        """
        try:
            # Check if comparison exists
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='comparison'")
            if not self.cursor.fetchone():
                return self.get_random_recommendations(file_name, count)

            # 1. Get the ID for the current file_name
            self.cursor.execute("SELECT id FROM file_info WHERE file_name = ?", (file_name,))
            row = self.cursor.fetchone()
            if not row:
                return self.get_random_recommendations(file_name, count)
            
            current_id = row['id'] if isinstance(row, sqlite3.Row) else row[0]
            title_id = f"title_{current_id}"

            # 2. Query comparison and join with file_info to get names
            # We search both source_id and target_id because the matrix is upper-triangle only
            query = """
                WITH reco_ids AS (
                    SELECT target_id as other_id, distance FROM comparison WHERE source_id = ?
                    UNION ALL
                    SELECT source_id as other_id, distance FROM comparison WHERE target_id = ?
                )
                SELECT f.file_name, r.distance
                FROM reco_ids r
                JOIN file_info f ON 'title_' || f.id = r.other_id
                ORDER BY r.distance DESC
                LIMIT ?
            """
            self.cursor.execute(query, (title_id, title_id, count))
            results = self.cursor.fetchall()

            if results:
                return [(row['file_name'] if isinstance(row, sqlite3.Row) else row[0], 
                         row['distance'] if isinstance(row, sqlite3.Row) else row[1]) for row in results]
            
            return self.get_random_recommendations(file_name, count)
            
        except sqlite3.Error as e:
            print(f"Error getting recommendations: {e}")
            return self.get_random_recommendations(file_name, count)
    
    def get_random_recommendations(self, file_name: str, count: int = 10) -> List[Tuple[str, float]]:
        """Fallback: get other random files as recommendations"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT file_name 
                FROM file_info 
                WHERE file_name != ? 
                ORDER BY RANDOM() 
                LIMIT ?
            """, (file_name, count))
            
            results = self.cursor.fetchall()
            # Return with sequential distance scores (just for ranking)
            return [(row[0], 1.0 - (i * 0.05)) for i, row in enumerate(results)]
        except sqlite3.Error as e:
            print(f"Error in fallback recommendations: {e}")
            return []
    
    def get_database_schema(self) -> dict:
        """Get database schema information"""
        try:
            schema = {}
            
            # Get all table names
            self.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table'
            """)
            tables = self.cursor.fetchall()
            
            for table_row in tables:
                table_name = table_row[0]
                
                # Get columns for each table
                self.cursor.execute(f"PRAGMA table_info({table_name})")
                columns = self.cursor.fetchall()
                
                schema[table_name] = [
                    {
                        'name': col[1],
                        'type': col[2],
                        'not_null': col[3],
                        'default': col[4],
                        'pk': col[5]
                    }
                    for col in columns
                ]
            
            return schema
        except sqlite3.Error as e:
            print(f"Error getting schema: {e}")
            return {}
    
    def get_table_stats(self, table_name: str) -> dict:
        """Get statistics for a table"""
        try:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = self.cursor.fetchone()[0]
            
            return {
                'table': table_name,
                'row_count': count
            }
        except sqlite3.Error as e:
            print(f"Error getting table stats: {e}")
            return {}

    def get_pdf_tags(self, file_name: str) -> List[Tuple[str, float]]:
        """Get tags/topics for a PDF from tags_full table"""
        try:
            # 1. Get the ID for the current file_name
            self.cursor.execute("SELECT id FROM file_info WHERE file_name = ?", (file_name,))
            row = self.cursor.fetchone()
            if not row:
                return []
            
            current_id = row['id'] if isinstance(row, sqlite3.Row) else row[0]
            title_id = f"title_{current_id}"

            # 2. Query tags_full
            self.cursor.execute("""
                SELECT topic, distance FROM tags_full 
                WHERE ID = ? 
                ORDER BY distance DESC
            """, (title_id,))
            
            results = self.cursor.fetchall()
            return [(row['topic'] if isinstance(row, sqlite3.Row) else row[0], 
                     row['distance'] if isinstance(row, sqlite3.Row) else row[1]) for row in results]
        except sqlite3.Error as e:
            print(f"Error fetching tags: {e}")
            return []
