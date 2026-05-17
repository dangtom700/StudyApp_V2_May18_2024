"""
PDF → TXT Converter
Reads PDFs from READING_LIST_PATH, extracts plain text, and writes
one .txt file per PDF into RAW_DATA_PATH — which is where the
extract_text pipeline expects to find its input files.

Reads path config from .env (if present) with the same fallbacks used
by the rest of the pipeline (path.py / env.hpp).
"""

import os
import sys
import concurrent.futures as cf
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import modules.path as _path

# --- Path resolution (uses the same source of truth as the rest of the pipeline) ---
PDF_SRC  = Path(_path.pdf_path)
TXT_DEST = Path(_path.source_data)

# --- Extraction backend: prefer PyMuPDF (faster, better quality); fall back to pypdf ---
try:
    import fitz  # PyMuPDF
    def _extract(pdf_path: Path) -> str:
        doc = fitz.open(str(pdf_path))
        pages = (doc[i].get_text("text") for i in range(len(doc)))
        return "\n".join(pages)
    BACKEND = "PyMuPDF"
except ImportError:
    try:
        from pypdf import PdfReader
        def _extract(pdf_path: Path) -> str:
            reader = PdfReader(str(pdf_path))
            return "\n".join(
                (page.extract_text() or "") for page in reader.pages
            )
        BACKEND = "pypdf"
    except ImportError:
        print("[ERROR] Neither PyMuPDF nor pypdf is installed.")
        print("  Install one:  pip install pypdf   or   pip install pymupdf")
        sys.exit(1)


def convert_one(pdf_path: Path, dest_dir: Path) -> tuple[str, bool, str]:
    """Convert a single PDF to .txt. Returns (filename, success, message)."""
    txt_path = dest_dir / (pdf_path.stem + ".txt")

    if txt_path.exists() and txt_path.stat().st_size > 0:
        return pdf_path.name, True, "skip (already done)"

    try:
        text = _extract(pdf_path).strip()
        if not text:
            return pdf_path.name, False, "no text extracted (scanned image?)"

        txt_path.write_text(text, encoding="utf-8")
        return pdf_path.name, True, f"ok ({len(text):,} chars)"

    except Exception as e:
        return pdf_path.name, False, str(e)


def convert_all(src: Path = PDF_SRC, dest: Path = TXT_DEST, workers: int = 4) -> None:
    if not src.exists():
        print(f"[ERROR] Source folder not found: {src}")
        print("  Set READING_LIST_PATH in your .env file.")
        sys.exit(1)

    dest.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(src.glob("*.pdf"))
    if not pdfs:
        print(f"[INFO] No PDF files found in: {src}")
        return

    print(f"Backend : {BACKEND}")
    print(f"Source  : {src}")
    print(f"Output  : {dest}")
    print(f"PDFs    : {len(pdfs)}")
    print()

    ok = skip = fail = 0

    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(convert_one, p, dest): p for p in pdfs}
        for i, future in enumerate(cf.as_completed(futures), 1):
            name, success, msg = future.result()
            if "skip" in msg:
                skip += 1
            elif success:
                ok += 1
            else:
                fail += 1
            tag = "SKIP" if "skip" in msg else ("OK" if success else "FAIL")
            print(f"  [{i:>4}/{len(pdfs)}] [{tag:<4}] {name[:60]:<60}  {msg}")

    print()
    print(f"Done — {ok} converted, {skip} skipped, {fail} failed.")
    print(f"Text files written to: {dest}")


if __name__ == "__main__":
    convert_all()
