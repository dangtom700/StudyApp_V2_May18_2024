# 🚀 QUICK START GUIDE

## What is this?

You now have a **desktop app** that lets you:
- 📄 **Preview PDFs** from your reading list
- 🔍 **Search** for specific content across all PDFs
- 💡 **Get recommendations** for similar/dissimilar PDFs

## How to Start?

### Step 1: Create Conda Environment
```bash
conda env create -f env.yml
```

### Step 2: Activate Environment & Verify Setup
```bash
conda activate study_app_env
python verify_install.py
```
This will check everything and tell you if you're ready!

### Step 3: Launch App
```bash
run_app.bat        # Windows
bash run_app.sh    # Mac/Linux
```

✅ **Done!** The app is now running.

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

- [ ] Database exists at `app/data/pdf_text.db`
- [ ] PDFs indexed or available at: `D:\READING LIST`
- [ ] Run `python verify_install.py` ✓
- [ ] Read `app/APP_GUIDE.md` as you use it

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
| Database | `app/data/pdf_text.db` |
| App Code | `app/src/pdf_app.py` |
| Database Module | `app/src/database_manager.py` |

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
- Run `python inspect_db.py` to verify database structure

**"Search returns nothing"**
- Try simpler keywords
- PDFs might not be indexed yet
- Use different search terms

**"PyQt5 won't install"**
```bash
# Windows
pip install --upgrade pyqt5

# Linux
sudo apt-get install python3-pyqt5
```

## Full Documentation

See `app/APP_GUIDE.md` for complete documentation

---

**Ready? Run the app now!** 🎯