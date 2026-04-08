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
        Get recommendations for a file based on item_matrix distances
        Returns files with greatest distance (most dissimilar)
        Format: [(recommended_file_name, distance_score), ...]
        """
        try:
            # First, try to get recommendations from item_matrix table
            # This assumes item_matrix has columns: file_id1, file_id2, distance
            # We need to join with file info to get file names
            
            self.cursor.execute("""
                SELECT DISTINCT target_name FROM item_matrix 
                WHERE source_name = (SELECT target_name FROM item_matrix WHERE source_name = ? LIMIT 1)
                LIMIT 1
            """, (file_name,))
            
            # Check if item_matrix exists and has the expected structure
            self.cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='item_matrix'
            """)
            
            if not self.cursor.fetchone():
                # Fallback: return random dissimilar files (all files except current)
                return self.get_random_recommendations(file_name, count)
            
            # Try to get distances from item_matrix
            self.cursor.execute("""
                SELECT 
                    CASE 
                        WHEN source_name = ? THEN target_name 
                        ELSE source_name 
                    END as other_file,
                    distance
                FROM item_matrix 
                WHERE target_name = ? OR source_name = ?
                ORDER BY distance DESC 
                LIMIT ?
            """, (file_name, file_name, file_name, count))
            
            results = self.cursor.fetchall()
            if results:
                return [(row[0], row[1]) for row in results]
            
            # Fallback if no results
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
