"""
Markdown note extraction

The behaviour is similiar to pdf extraction with the aim is to help assist the
word frequency feeding and boosting the trend and likihood of certain keywords.

Process
1. Starting of with batch collect files (already build)
2. Text extraction in Markdown file
2.1. Set the text chunk size
2.2. Set the table for storage (may be use the table in pdf chunk)
2.3. Chunking text into 800 characters
2.4. Store the chunk in the table
"""
from modules.extract_pdf import batch_collect_files, store_chunks_in_db
import re
import markdown
import sqlite3
import os
from modules.path import chunk_database_path

def extract_text_chunk(file, chunk_size=8000):
    """Extracts and cleans text chunk by chunk from a markdown file."""
    content = []
    for line in file:
        content.append(line)
        if sum(len(c) for c in content) >= chunk_size:
            yield ''.join(content)
            content = []
    
    if content:
        yield ''.join(content)

def clean_markdown_text(markdown_text):
    """Converts markdown text to plain text by removing HTML tags."""
    html_content = markdown.markdown(markdown_text)
    text = re.sub(r'<[^>]+>', '', html_content)
    return text

CHUNK_SIZE = 800  # Character limit for each chunk stored in the database

def extract_markdown_notes_in_batches(directory):
    """Main process to collect, extract, chunk, and store markdown files."""
    conn = sqlite3.connect(chunk_database_path)
    
    for file_path in batch_collect_files(folder_path= directory, extension= '.md'):
        with open(file_path, 'r', encoding='utf-8') as file:
            for raw_chunk in extract_text_chunk(file):
                text = clean_markdown_text(raw_chunk)
                chunks = [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
                store_chunks_in_db(file_name= os.path.basename(file_path), chunks= chunks, db_name= chunk_database_path)