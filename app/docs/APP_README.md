# 📚 Study App - PDF Manager & Recommendation System

A powerful desktop application for managing, searching, and discovering insights from your PDF library.

## ✨ Features

### 1. 📄 **PDF Viewer**
- Browse all indexed PDFs in your collection
- View file metadata (path, chunk count)
- Quick preview of content
- Organized file listing

### 2. 🔍 **Full-Text Search**
- Search across all PDF content
- Case-insensitive keyword matching
- Configurable result count
- Jump to specific chunks
- See context around matches

### 3. 💡 **Smart Recommendations**
- Discover dissimilar content for cross-disciplinary learning
- Powered by document distance metrics
- Get recommendations based on current reading
- Unique discovery algorithm using greatest distance

## 🚀 Quick Start

### Installation (60 seconds)

```bash
# 1. Install dependencies
pip install -r app_requirements.txt

# 2. Verify database
python inspect_db.py

# 3. Launch app
run_app.bat                    # Windows
# OR
bash run_app.sh               # Mac/Linux
```

### First Use

1. **📄 PDF Viewer** tab: Explore your collection
2. **🔍 Search** tab: Find topics of interest  
3. **💡 Recommendations** tab: Discover new areas

See [QUICK_START.md](QUICK_START.md) for detailed setup.

## 📦 Project Structure

```
StudyApp_V2_May18_2024/
├── src/
│   ├── pdf_app.py                 # Main PyQt5 application
│   ├── database_manager.py         # Database operations
│   ├── main.py                     # Pipeline orchestrator
│   └── modules/
│       ├── path.py                 # Path configuration
│       ├── extract_text.py         # PDF text extraction
│       ├── word_freq.py            # Word frequency analysis
│       └── tf_idf.py               # TF-IDF computation
│
├── data/
│   ├── pdf_text.db                 # SQLite database (chunks, vectors, etc)
│   ├── pdf_text.db-shm             # Database snapshot
│   ├── pdf_text.db-wal             # Database write-ahead log
│   └── token_json/                 # Token indices
│
├── docs/
│   └── ...                          # Additional documentation
│
├── app_requirements.txt             # Python dependencies
├── run_app.bat                      # Windows launcher
├── run_app.sh                       # Mac/Linux launcher
├── inspect_db.py                    # Database inspector utility
├── analyze_recommendations.py       # Recommendation analyzer
├── QUICK_START.md                   # Quick setup (start here!)
├── APP_GUIDE.md                     # Complete user guide
├── SETUP_CONFIG.md                  # Configuration & troubleshooting
└── README.md                        # This file
```

## 🎯 Key Components

### Core Application
- **pdf_app.py**: Main PyQt5 GUI with 3 tabbed interfaces
- **database_manager.py**: SQLite database abstraction layer

### Database Tables
| Table | Purpose | Required |
|-------|---------|----------|
| `chunks` | PDF text content | ✓ Yes |
| `item_matrix` | Document distances | • Recommended |
| `tfidf_vectors` | TF-IDF weights | • Optional |
| `tokens` | Term index | • Optional |
| `word_frequency` | Word stats | • Optional |

## 📋 Common Tasks

### Access Database
```bash
# Inspect structure and content
python inspect_db.py

# Analyze recommendations
python analyze_recommendations.py
```

### Extract PDFs
```bash
# Extract text from PDFs in D:\READING LIST
python src/main.py --extractText

# Compute TF-IDF for better recommendations
python src/main.py --computeTFIDF
```

### Search Operations
- Go to **Search Files** tab
- Enter keyword (case-insensitive)
- Adjust max results (1-1000)
- Click **Search**

### Get Recommendations
- Go to **Recommendations** tab
- Select a PDF file
- Click **Generate Recommendations**
- View files with greatest distance (most dissimilar)

## ⚙️ Configuration

### Change PDF Source Folder
Edit `src/modules/path.py`:
```python
pdf_path = "D:\\READING LIST"  # Change this path
```

### Adjust Chunk Size
Edit `src/main.py`:
```python
chunk_size = 1024  # Characters per chunk
# Options: 256, 512, 1024, 2048
```

### Database Location
Edit `src/modules/path.py`:
```python
chunk_database_path = r"C:\path\to\pdf_text.db"
```

See [SETUP_CONFIG.md](SETUP_CONFIG.md) for advanced configuration.

## 🔧 Troubleshooting

### "No PDFs found"
```bash
# Check database
python inspect_db.py

# Extract PDFs if needed
python src/main.py --extractText
```

### "Search is slow"
- Reduce max results in Search tab
- Use more specific keywords
- Check database indices exist

### "Recommendations not working"
```bash
# Check item_matrix
python analyze_recommendations.py

# Compute TF-IDF if needed
python src/main.py --computeTFIDF
```

### "PyQt5 installation fails"
```bash
# Try explicit upgrade
pip install --upgrade PyQt5

# Or on Linux
sudo apt-get install python3-pyqt5
```

See [SETUP_CONFIG.md](SETUP_CONFIG.md) for more troubleshooting.

## 📊 Performance

### Typical Performance
- **Search**: ~1-2 seconds for 10,000+ chunks
- **Recommendations**: ~2-5 seconds for 1000+ files
- **UI**: Always responsive (async-ready architecture)

### Optimize For Large Collections (10,000+ PDFs)

1. Create database indices:
```bash
sqlite3 data/pdf_text.db
# Run these SQL commands:
CREATE INDEX idx_file_name ON chunks(file_name);
CREATE INDEX idx_text_content ON chunks(text_content);
```

2. Reduce chunk size in extraction
3. Limit search results to 20-50

## 🔐 Database Backup

### Backup All Database Files
```bash
# Windows
xcopy data\pdf_text.db* backup\ /Y

# Mac/Linux
cp data/pdf_text.db* backup/
```

### Important
- Always backup all three files together:
  - `pdf_text.db`
  - `pdf_text.db-shm`
  - `pdf_text.db-wal`

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [QUICK_START.md](QUICK_START.md) | 2-minute setup guide |
| [APP_GUIDE.md](APP_GUIDE.md) | Complete user documentation |
| [SETUP_CONFIG.md](SETUP_CONFIG.md) | Configuration & advanced setup |

## 🛠️ Utilities

### Database Inspection
```bash
python inspect_db.py
```
- View all tables and schemas
- Check row counts
- Sample data inspection
- Requirement verification

### Recommendation Analysis
```bash
python analyze_recommendations.py
```
- Check item_matrix status
- Verify PDF indexing
- Analyze TF-IDF data
- Show recommendation queries

## 💡 Use Cases

### For Students
- Organize research papers
- Cross-reference topics
- Discover interdisciplinary connections
- Quick content lookup

### For Researchers
- Manage literature library
- Find similar/dissimilar papers
- Track content across documents
- Full-text paper search

### For Knowledge Workers
- Organize reading list
- Quick reference lookup
- Topic discovery
- Learning through serendipity

## 🔮 Future Features

- [ ] PDF rendering inside app (view actual PDFs)
- [ ] Advanced search (boolean operators, regex)
- [ ] Tagging and categorization
- [ ] Reading history and bookmarks
- [ ] Export search results
- [ ] Dark mode theme
- [ ] Multi-database support
- [ ] Machine learning recommendations

## 🤝 Contributing

To improve the app:

1. **Suggest features**: Add to [SETUP_CONFIG.md](SETUP_CONFIG.md) "Future Enhancements"
2. **Report bugs**: Describe issue with `python inspect_db.py` output
3. **Optimize**: Profile with `python -m cProfile pdf_app.py`

## 📝 License

Part of Study App V2 project (May 18, 2024)

## ❓ Support

1. **Quick questions**: See [QUICK_START.md](QUICK_START.md)
2. **How-to guides**: See [APP_GUIDE.md](APP_GUIDE.md)
3. **Setup issues**: See [SETUP_CONFIG.md](SETUP_CONFIG.md)
4. **Database help**: Run `python inspect_db.py`
5. **Recommendations help**: Run `python analyze_recommendations.py`

---

**Ready to get started?**

```bash
# Quick setup
pip install -r app_requirements.txt

# Verify
python inspect_db.py

# Launch!
run_app.bat  # Windows
bash run_app.sh  # Mac/Linux
```

🎯 **Let's organize and explore your reading library!**
