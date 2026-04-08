"""
Installation Verification Script
Verify all components and dependencies are properly installed
Run from parent directory of app folder
"""

import sys
from pathlib import Path


def check_python_version():
    """Check Python version"""
    print("Checking Python version...")
    version = sys.version_info
    print(f"  Python: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or version.minor < 7:
        print("  ✗ Python 3.7+ required!")
        return False

    print("  ✓ OK\n")
    return True


def check_file_exists(path, description):
    """Check if a file exists"""
    if Path(path).exists():
        print(f"  ✓ {description}: {path}")
        return True
    else:
        print(f"  ✗ {description} NOT FOUND: {path}")
        return False


def check_directory(path, description):
    """Check if a directory exists"""
    if Path(path).is_dir():
        print(f"  ✓ {description}: {path}")
        return True
    else:
        print(f"  ✗ {description} NOT FOUND: {path}")
        return False


def check_dependencies():
    """Check Python dependencies"""
    print("\nChecking Python dependencies...")

    dependencies = {
        'PyQt5': 'PyQt5',
        'fitz': 'PyMuPDF',
        'sqlite3': 'sqlite3 (built-in)',
        'tabulate': 'tabulate',
    }

    all_ok = True

    for module, name in dependencies.items():
        try:
            __import__(module)
            print(f"  ✓ {name}")
        except ImportError:
            print(f"  ✗ {name} NOT INSTALLED")
            print(f"    Install: conda install {name}")
            all_ok = False

    print()
    return all_ok


def check_file_structure():
    """Check project file structure"""
    print("Checking file structure...")

    files_to_check = [
        ('app/src/pdf_app.py', 'Main app'),
        ('app/src/database_manager.py', 'Database manager'),
        ('app/src/main.py', 'Pipeline'),
        ('app/src/modules/path.py', 'Path config'),
        ('app/src/modules/extract_text.py', 'Extract text module'),
        ('app/data/pdf_text.db', 'SQLite database'),
        ('app/app_requirements.txt', 'Requirements'),
    ]

    all_ok = True
    for file_path, description in files_to_check:
        if not check_file_exists(file_path, description):
            all_ok = False

    print()
    return all_ok


def check_database():
    """Check database connectivity and content"""
    print("\nChecking database...")

    try:
        import sqlite3
        db_path = Path('app/data/pdf_text.db')

        if not db_path.exists():
            print(f"  ✗ Database not found: {db_path}")
            return False

        print(f"  ✓ Database file exists: {db_path}")

        # Connect to database
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check chunks table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='chunks'
        """)

        if cursor.fetchone():
            print("  ✓ chunks table found")

            # Get count
            cursor.execute("SELECT COUNT(*) FROM chunks")
            count = cursor.fetchone()[0]
            print(f"  ✓ {count} text chunks indexed")

            # Get unique files
            cursor.execute("SELECT COUNT(DISTINCT file_name) FROM chunks")
            unique = cursor.fetchone()[0]
            print(f"  ✓ {unique} unique PDF files")
        else:
            print("  ✗ chunks table NOT found")
            conn.close()
            return False

        # Check item_matrix
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='item_matrix'
        """)

        if cursor.fetchone():
            print("  ✓ item_matrix table found (recommendations enabled)")
        else:
            print("  • item_matrix NOT found (recommendations will use fallback)")

        conn.close()
        print()
        return True

    except Exception as e:
        print(f"  ✗ Database error: {e}")
        print()
        return False


def check_pdf_source():
    """Check PDF source folder"""
    print("Checking PDF source...")

    pdf_source = Path("D:/READING LIST")

    if pdf_source.exists():
        pdfs = list(pdf_source.glob("*.pdf"))
        print(f"  ✓ PDF folder exists: {pdf_source}")
        print(f"  ✓ {len(pdfs)} PDF files found")
        print()
        return True
    else:
        print(f"  • PDF folder not found: {pdf_source}")
        print("    (This is OK - database can still have extracted PDFs)")
        print()
        return True


def show_next_steps(all_ok):
    """Show next steps"""
    print("=" * 70)
    print("NEXT STEPS")
    print("=" * 70)

    if all_ok:
        print("""
✓ All checks passed!

You're ready to launch the app:

  # Windows
  run_app.bat

  # Mac/Linux
  bash run_app.sh
        """)
    else:
        print("""
✗ Some checks failed. Fix these issues:

1. Missing conda environment?
   conda env create -f env.yml

2. Missing database?
   conda activate study_app_env
   cd app/src && python main.py --extractText

3. Missing files?
   Check app/ folder structure

For more help, see:
  • QUICK_START.md - Setup guide
  • APP_GUIDE.md - User guide
  • SETUP_CONFIG.md - Configuration
        """)


def main():
    """Run all checks"""
    print("=" * 70)
    print("📚 STUDY APP - INSTALLATION VERIFICATION")
    print("=" * 70)
    print()

    checks = [
        ("Python Version", check_python_version),
        ("Project Files", check_file_structure),
        ("Dependencies", check_dependencies),
        ("Database", check_database),
        ("PDF Source", check_pdf_source),
    ]

    results = {}
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"✗ Error during {check_name}: {e}\n")
            results[check_name] = False

    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)

    for check_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} {check_name}")

    all_ok = all(results.values())
    print()

    show_next_steps(all_ok)

    print("=" * 70)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())