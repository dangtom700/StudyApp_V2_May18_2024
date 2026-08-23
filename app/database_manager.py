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
        self._has_catalog = None      # resolved lazily by has_catalog()
        self.connect()
    
    def connect(self):
        """Connect to database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Must be set BEFORE the cursor is created -- a cursor keeps the factory it
            # was built with, so setting this afterwards left every row a plain tuple.
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    # ---- Book catalog -------------------------------------------------------
    # v_book is built by `python src/main.py --buildCatalog`. Everything below
    # degrades to the old hash-only behaviour when it hasn't been built yet, so the
    # app still runs on a database that predates the catalog.

    def has_catalog(self) -> bool:
        """True once --buildCatalog has run. Checked once, then cached."""
        if self._has_catalog is None:
            try:
                self.cursor.execute("SELECT 1 FROM v_book LIMIT 1")
                self._has_catalog = self.cursor.fetchone() is not None
            except sqlite3.Error:
                self._has_catalog = False
        return self._has_catalog

    def display_name(self, hash_id: str) -> str:
        """Human-readable label for a hash. Falls back to the hash itself."""
        if not self.has_catalog():
            return hash_id
        try:
            self.cursor.execute("SELECT title FROM v_book WHERE hash_id = ?", (hash_id,))
            row = self.cursor.fetchone()
            return (row[0] or hash_id) if row else hash_id
        except sqlite3.Error:
            return hash_id

    def display_names(self, hash_ids: List[str]) -> dict:
        """Bulk display_name -- one query for a whole result list, not one per row."""
        labels = {h: h for h in hash_ids}
        if not hash_ids or not self.has_catalog():
            return labels

        try:
            placeholders = ','.join('?' * len(hash_ids))
            self.cursor.execute(
                f"SELECT hash_id, title FROM v_book WHERE hash_id IN ({placeholders})",
                hash_ids)
            for row in self.cursor.fetchall():
                if row[1]:
                    labels[row[0]] = row[1]
        except sqlite3.Error as e:
            print(f"Error fetching titles: {e}")
        return labels

    def get_catalog_row(self, hash_id: str) -> Optional[dict]:
        """Every catalog field for one book, or None if the catalog isn't built."""
        if not self.has_catalog():
            return None
        try:
            self.cursor.execute("SELECT * FROM v_book WHERE hash_id = ?", (hash_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Error fetching catalog row: {e}")
            return None

    def get_domains(self) -> List[str]:
        """Subject domains present in the library, most populated first."""
        if not self.has_catalog():
            return []
        try:
            self.cursor.execute("""
                SELECT domain, COUNT(*) AS n FROM v_book
                WHERE domain IS NOT NULL
                GROUP BY domain ORDER BY n DESC
            """)
            return [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error fetching domains: {e}")
            return []

    def search_catalog(self, text: str = "", domain: Optional[str] = None,
                       max_results: int = 200) -> List[Tuple[str, str]]:
        """
        Search books by title/topic and/or domain -- metadata only, not chunk text.
        Returns [(hash_id, title), ...].
        """
        if not self.has_catalog():
            return []

        clauses, params = [], []
        if text:
            clauses.append("(title LIKE ? OR topics LIKE ?)")
            params += [f"%{text}%", f"%{text}%"]
        if domain:
            clauses.append("domain = ?")
            params.append(domain)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max_results)

        try:
            self.cursor.execute(
                f"SELECT hash_id, title FROM v_book {where} "
                f"ORDER BY title LIMIT ?", params)
            return [(row[0], row[1] or row[0]) for row in self.cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Error searching catalog: {e}")
            return []

    def get_all_pdfs(self) -> List[Tuple[str, str]]:
        """
        Every book in the library as [(hash_id, label), ...].

        Reads the catalog when it exists -- which orders by title and includes books
        that were never text-extracted -- and falls back to file_info otherwise.
        """
        try:
            if self.has_catalog():
                self.cursor.execute("""
                    SELECT hash_id, COALESCE(NULLIF(title, ''), hash_id) AS label
                    FROM v_book ORDER BY label COLLATE NOCASE
                """)
            else:
                self.cursor.execute("""
                    SELECT DISTINCT file_name, file_name FROM file_info
                    ORDER BY file_name
                """)
            return [(row[0], row[1]) for row in self.cursor.fetchall()]
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

    def get_all_tags(self) -> List[str]:
        """Get all unique tags/topics available in the database"""
        try:
            self.cursor.execute("""
                SELECT DISTINCT topic FROM tags_full 
                ORDER BY topic
            """)
            results = self.cursor.fetchall()
            return [row['topic'] if isinstance(row, sqlite3.Row) else row[0] for row in results]
        except sqlite3.Error as e:
            print(f"Error fetching all tags: {e}")
            return []

    def search_files_by_tag(self, tag: str, max_results: int = 50) -> List[Tuple[str, float]]:
        """
        Search for files that have a specific tag
        Returns: [(file_name, tag_relevance_score), ...]
        """
        try:
            self.cursor.execute("""
                SELECT DISTINCT f.file_name, t.distance
                FROM tags_full t
                JOIN file_info f ON 'title_' || f.id = t.ID
                WHERE LOWER(t.topic) = LOWER(?)
                ORDER BY t.distance DESC
                LIMIT ?
            """, (tag, max_results))
            
            results = self.cursor.fetchall()
            return [(row['file_name'] if isinstance(row, sqlite3.Row) else row[0],
                     row['distance'] if isinstance(row, sqlite3.Row) else row[1]) for row in results]
        except sqlite3.Error as e:
            print(f"Error searching files by tag: {e}")
            return []

    def search_files_by_tags(self, tags: List[str], match_all: bool = False, max_results: int = 50) -> List[Tuple[str, float]]:
        """
        Search for files that have specific tags
        Args:
            tags: List of tag names to search for
            match_all: If True, returns only files with ALL tags; if False, returns files with ANY tag
            max_results: Maximum number of results
        Returns: [(file_name, combined_relevance_score), ...]
        """
        try:
            if not tags:
                return []
            
            # Create placeholders for SQL
            placeholders = ','.join(['?' for _ in tags])
            lower_tags = [t.lower() for t in tags]
            
            if match_all:
                # Files must have ALL specified tags
                query = f"""
                    SELECT f.file_name, AVG(t.distance) as avg_distance
                    FROM tags_full t
                    JOIN file_info f ON 'title_' || f.id = t.ID
                    WHERE LOWER(t.topic) IN ({placeholders})
                    GROUP BY f.file_name
                    HAVING COUNT(DISTINCT LOWER(t.topic)) = ?
                    ORDER BY avg_distance DESC
                    LIMIT ?
                """
                self.cursor.execute(query, lower_tags + [len(tags), max_results])
            else:
                # Files can have ANY of the specified tags
                query = f"""
                    SELECT f.file_name, MAX(t.distance) as max_distance
                    FROM tags_full t
                    JOIN file_info f ON 'title_' || f.id = t.ID
                    WHERE LOWER(t.topic) IN ({placeholders})
                    GROUP BY f.file_name
                    ORDER BY max_distance DESC
                    LIMIT ?
                """
                self.cursor.execute(query, lower_tags + [max_results])
            
            results = self.cursor.fetchall()
            return [(row['file_name'] if isinstance(row, sqlite3.Row) else row[0],
                     row['avg_distance'] if match_all else row['max_distance'] if isinstance(row, sqlite3.Row) else row[1]) 
                    for row in results]
        except sqlite3.Error as e:
            print(f"Error searching files by multiple tags: {e}")
            return []
