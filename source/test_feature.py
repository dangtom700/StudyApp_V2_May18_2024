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
from modules.extract_pdf import batch_collect_files
import re
import markdown

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

def store_chunks(conn, file_name, chunk):
    """Stores a chunk of text into the database."""
    cursor = conn.cursor()
    cursor.execute('INSERT INTO pdf_chunks (file_name, chunk) VALUES (?, ?)', (file_name, chunk))
    conn.commit()
