# 📋 SETUP CHECKLIST & CONFIGURATION

## Pre-Launch Verification

Before running the app, use these tools to verify your setup:

### 1. Inspect Database
```bash
python inspect_db.py
```
This checks:
- ✓ Database connection
- ✓ All available tables
- ✓ Table schemas
- ✓ Row counts in each table
- ✓ App requirements met

**What to look for:**
- "chunks" table should exist
- "chunks" should have: file_name, file_path, chunk_id, text_content

### 2. Analyze Recommendations
```bash
python analyze_recommendations.py
```
This checks:
- ✓ item_matrix table status
- ✓ Number of PDF files indexed
- ✓ TF-IDF data availability
- ✓ Recommendation query validation

**What to look for:**
- If "item_matrix" exists → Recommendations are powered by real similarity data
- If missing → Recommendations use fallback (random files)
- Number of unique files in chunks table

## Setup Checklist

- [ ] **Database Exists**
  - File: `data/pdf_text.db`
  - Run: `python inspect_db.py` to verify

- [ ] **PDFs Indexed**
  - Check: `D:\READING LIST` has PDF files
  - Run: `python inspect_db.py` → shows file count
  - If 0 files: Extract PDFs with `python src/main.py --extractText`

- [ ] **Dependencies Installed**
  - Run: `pip install -r app_requirements.txt`
  - Verify: `python -c "import PyQt5; import fitz; import tabulate"`

- [ ] **Database Tables Ready**
  - Required: ✓ chunks
  - Optional: • item_matrix, • tfidf_vectors, • tokens

- [ ] **App Folder Structure**
  - src/pdf_app.py
  - src/database_manager.py
  - src/modules/path.py
  - data/pdf_text.db

## Configuration Options

### Feature Enablement

**Maximum Search Results:**
- Default: 20
- Adjustable in Search tab (1-1000)
- More results = slower search

**Recommendation Count:**
- Default: 10
- Adjustable in Recommendations tab (1-50)
- Higher count = takes longer

### Database Configuration

Edit `src/modules/path.py` to customize paths:

```python
pdf_path = "D:\\READING LIST"              # PDF source location
chunk_database_path = "...\\data\\pdf_text.db"  # Database location
```

### PDF Extraction Settings

In `src/main.py`:

```python
chunk_size = 1024  # Characters per chunk
# Sizes:
# - 256-512: Quick lookup, less context
# - 512-1024: Balanced (recommended)
# - 1024-2048: More context, slower search
```

## Troubleshooting Configuration

### Problem: "No tables found"
**Solution:**
1. Verify database file exists: `data/pdf_text.db`
2. Check file isn't corrupted: `python inspect_db.py`
3. If corrupted, re-extract PDFs: `python src/main.py --extractText`

### Problem: "chunks table empty"
**Solution:**
1. Extract PDFs from source folder:
   ```bash
   python src/main.py --extractText
   ```
2. Verify PDFs exist in `D:\READING LIST`
3. Check extraction logs: `data/process.log`

### Problem: "Search very slow"
**Solution:**
1. Reduce "Max Results" in Search tab
2. Use more specific keywords
3. Check database is not corrupted: `python inspect_db.py`

### Problem: "Recommendations not working"
**Solution:**
1. Check item_matrix exists:
   ```bash
   python analyze_recommendations.py
   ```
2. If missing, compute TF-IDF:
   ```bash
   python src/main.py --computeTFIDF
   ```
3. App will use fallback recommendations if item_matrix unavailable

## Performance Tuning

### For Large Datasets (10,000+ PDFs)

1. **Create database indices:**
   ```sql
   CREATE INDEX idx_file_name ON chunks(file_name);
   CREATE INDEX idx_text_content ON chunks(text_content);
   ```

2. **Adjust chunk size** (smaller = faster search):
   ```python
   chunk_size = 512  # Instead of 1024
   ```

3. **Limit search results:**
   - Default to 10-20 instead of 100

### For Small Datasets (< 100 PDFs)

- Default settings are optimal
- No special tuning needed

## Database Schema Reference

### chunks Table
```
file_name      TEXT - PDF file name
file_path      TEXT - Full file path
chunk_id       INTEGER - Unique chunk identifier
text_content   TEXT - Extracted text (1024 chars)
created_at     DATETIME - When extracted
```

### item_matrix Table (if available)
```
file_name1     TEXT - First file
file_name2     TEXT - Second file
distance       REAL - Cosine distance (0-1)
                     Higher = more dissimilar
```

### Optional Tables
```
tfidf_vectors - TF-IDF weight vectors
tokens        - Tokenized terms
word_frequency - Word occurrence stats
```

## Data Migration

If moving database to different location:

1. Update `src/modules/path.py`:
   ```python
   chunk_database_path = "/new/path/pdf_text.db"
   ```

2. Copy database file to new location

3. Verify with: `python inspect_db.py`

## Backup & Recovery

### Backup Database
```bash
xcopy data\pdf_text.db* data\backup\ /Y
```

### Restore Database
```bash
xcopy data\backup\pdf_text.db* data\ /Y
```

### Multi-file Backup
The database creates WAL files (pdf_text.db-shm, pdf_text.db-wal)
- Always backup all three files together
- Keep them in the same directory

## Advanced Configuration

### Custom Recommendation Algorithm

Edit `src/database_manager.py` → `get_recommendations()`:

```python
def get_recommendations(self, file_name, count=10):
    # Modify SQL query here
    # Current: Uses greatest distance (dissimilar)
    # Alternative: Use cosine similarity (similar)
```

### Custom Search Algorithm

Edit `src/database_manager.py` → `search_files()`:

```python
def search_files(self, keyword, max_results=20):
    # Current: Uses LIKE (simple substring match)
    # Alternative: Full-text search with FTS5
```

## Support Resources

- `APP_GUIDE.md` - Complete user guide
- `QUICK_START.md` - Quick setup
- `inspect_db.py` - Database inspection
- `analyze_recommendations.py` - Recommendation analysis

---

**Ready to configure?** Start with `python inspect_db.py` 🚀
