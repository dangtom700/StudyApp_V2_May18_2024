# 🚀 QUICK START GUIDE

## What is this?

You now have a **desktop app** that lets you:
- 📄 **Preview PDFs** from your reading list
- 🔍 **Search** for specific content across all PDFs
- 💡 **Get recommendations** for similar/dissimilar PDFs

## How to Start?

### Step 1: Install Dependencies
```bash
pip install -r app_requirements.txt
```

### Step 2: Launch the App
**On Windows:**
```batch
run_app.bat
```

**On Mac/Linux:**
```bash
bash run_app.sh
```

**Or manually:**
```bash
cd src
python pdf_app.py
```

## What Happens Next?

A window opens with 3 tabs:

### Tab 1: 📄 PDF Viewer
- See all PDFs in your collection
- Get file info (path, number of chunks)
- Read preview of first content

### Tab 2: 🔍 Search Files
- Search for keywords
- Get matching chunks
- See preview of matches

### Tab 3: 💡 Recommendations
- Pick a PDF
- Get recommendations for *dissimilar* content
- Great for discovering new topics!

## First Run Checklist

- [ ] Database exists at `data/pdf_text.db`
- [ ] PDFs in `D:\READING LIST` have been indexed
- [ ] Run `inspect_db.py` to verify database (optional)

## Debug Database

If the app doesn't find PDFs, run:
```bash
python inspect_db.py
```

This will show:
- ✓ What tables exist
- ✓ How many PDFs are indexed
- ✓ Required vs optional tables
- ✓ Sample data from each table

## Document Locations

| Item | Location |
|------|----------|
| PDF Files | `D:\READING LIST` |
| Database | `data\pdf_text.db` |
| App Code | `src\pdf_app.py` |
| Database Module | `src\database_manager.py` |

## Tips

💡 **Preference for Dissimilar Content**  
The recommendations show files with the *greatest distance* - perfect for cross-disciplinary learning!

💡 **Full-Text Search**  
Search is case-insensitive and searches all extracted text

💡 **Multiple Results**  
Adjust "Max Results" numbers to see more/less items

## Having Issues?

**"No PDFs found"**
- Check that PDFs have been extracted to database
- Run `inspect_db.py` to verify database structure

**"Search returns nothing"**
- Try different keywords
- PDFs might not be indexed yet
- Check database with `inspect_db.py`

**"PyQt5 won't install"**
```bash
# Windows
pip install --upgrade pyqt5

# Linux
sudo apt-get install python3-pyqt5
```

## Full Documentation

See `APP_GUIDE.md` for complete documentation

---

**Ready? Run the app now!** 🎯
