# 📚 Study App - PDF Manager Guide

## Overview

Study App is a desktop application built with PyQt5 that helps you manage, search, and discover PDFs from your reading list. It features three main utilities:

1. **📄 PDF Viewer** - Browse your collection and preview PDF content
2. **🔍 Search Files** - Full-text search across all PDF chunks
3. **💡 Recommendations** - Discover dissimilar files for serendipitous learning

## Features

### 1. PDF Viewer Tab
- **View all PDFs** in your database at a glance
- **See file metadata**: name, file path, total chunks
- **Preview content** of each PDF (first 500 characters)
- **Refresh list** to sync with the latest database

### 2. Search Files Tab
- **Full-text search** across all text chunks
- **Instant results** displayed in a searchable list
- **Configurable result count** (1-1000 results)
- **Content preview** for each search result
- **Chunk information** including chunk ID for reference

### 3. Recommendations Tab
- **Select any file** from your collection
- **Generate recommendations** based on content dissimilarity (using item_matrix distances)
- **Distance scoring** shows how different recommended files are from your selection
- **Higher distances** = more dissimilar content = serendipitous discovery opportunities

## Installation

### Prerequisites
- Python 3.7+
- pip package manager

### Setup

**On Windows:**
```batch
run_app.bat
```

**On Linux/Mac:**
```bash
chmod +x run_app.sh
./run_app.sh
```

**Manual installation:**
```bash
pip install -r app_requirements.txt
cd src
python pdf_app.py
```

## Database Structure

The app uses three main database tables:

### `chunks`
- `file_name`: Name of the PDF
- `file_path`: Full file path
- `chunk_id`: Unique chunk identifier
- `text_content`: Extracted text content

### `item_matrix` (used for recommendations)
- `file_name1`: First file
- `file_name2`: Second file
- `distance`: Cosine distance between files

### Additional tables
- Word frequency tables
- TF-IDF vectors (if computed)
- Topic indices

## Usage Examples

### Finding PDFs about a specific topic
1. Go to **Search Files** tab
2. Enter a keyword (e.g., "machine learning", "climate change")
3. Set max results (default: 20)
4. Click **Search**
5. Click any result to see preview

### Exploring related content
1. Go to **Recommendations** tab
2. Select a file from "Select Base File"
3. Set recommendation count (default: 10)
4. Click **Generate Recommendations**
5. Click any recommendation to see similarity details

### Learning from dissimilar content
- The recommendations are based on **greatest distance** (most dissimilar)
- This promotes serendipitous discovery
- Higher distance scores = more novel/different content
- Use this for cross-disciplinary learning

## Tips & Tricks

- **Search operators**: Use partial keywords to find related topics
- **Batch operations**: Generate recommendations for multiple files to see patterns
- **Content preview**: Read preview text to decide which PDFs to focus on
- **Chunk viewing**: Each search result shows which chunk matched - useful for specific information hunting
- **Refresh regularly**: If PDFs are added to your collection, refresh the lists

## Data Sources

- **PDF Location**: `D:\READING LIST`
- **Database**: `data\pdf_text.db`
- **Item Matrix**: Used for computing dissimilarity scores

## Troubleshooting

### "Database connection error"
- Ensure `data\pdf_text.db` exists
- Check file permissions
- Verify database hasn't been corrupted

### "No results" in search
- Try simpler keywords
- Check that chunks have been extracted from PDFs
- Use different search terms

### Recommendations not appearing
- The app will use random fallback recommendations if item_matrix is not available
- Check database schema with debug tools
- Generate recommendations may take a moment on large datasets

### PyQt5 won't install
```bash
# On Windows, try:
pip install --upgrade pyqt5

# On Linux, may need system packages:
sudo apt-get install python3-pyqt5
```

## Architecture

```
pdf_app.py
├── StudyAppWindow (Main container)
├── PDFViewerTab (PDF management)
├── FileSearchTab (Full-text search)
├── RecommendationTab (Content discovery)
└── database_manager.py (Database operations)
    ├── get_all_pdfs()
    ├── search_files()
    ├── get_recommendations()
    └── get_pdf_info()
```

## Performance Notes

- **Search** across 10,000+ chunks: ~1-2 seconds
- **Recommendations** for 1000+ files: ~2-5 seconds
- Database indices are used for optimization
- UI remains responsive during operations

## Future Enhancements

- [ ] PDF content rendering (view actual PDF inside app)
- [ ] Advanced search with boolean operators
- [ ] Tag/category filtering
- [ ] Reading history and bookmarks
- [ ] Export search results
- [ ] Dark mode UI theme

## Keyboard Shortcuts

- `Ctrl+S`: Focus search input
- `Enter`: Perform search
- `Ctrl+R`: Refresh file list
- `Escape`: Clear selection

## Support

For issues or questions:
1. Check database schema: `database_manager.py -> get_database_schema()`
2. Review database stats: `database_manager.py -> get_table_stats()`
3. Check `data\process.log` for ETL issues
4. Verify PDF at: `D:\READING LIST`
