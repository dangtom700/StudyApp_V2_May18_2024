"""
modules/compress_pdf.py  --  Ghostscript PDF compression as a pipeline stage.

Purpose
-------
Shrink the PDFs in READING_LIST_PATH *in place*, before the rest of the pipeline
reads them.

Wire-up (already done in src/main.py)
-------------------------------------
    python src/main.py --compressPDF                    # compress the reading list
    python src/main.py --compressPDF --compressDryRun   # list what would be done
    python src/main.py --compressPDF --compressPreset screen --compressJobs 8

Why the name must not change
----------------------------
`file_info.id` is md5 of the file's STEM (create_unique_id in
src/lib/updateDB.hpp), and modules/catalog.py joins everything through
`hash_id` == that same stem. So the whole key chain -- file_token, tags,
tags_full, comparison, item_matrix, relation_distance_filtered -- follows the
filename and nothing else.

Compression may therefore write wherever it likes as long as each book keeps its
name; the library as a whole can be moved to another folder without re-keying
anything. Renaming a file is what breaks the chain, which is why this stage
rewrites each PDF under its existing stem and never re-hashes the compressed
bytes. (Until 2026-08-27 the id was md5 of the file's ABSOLUTE PATH, and moving
the library orphaned every derived table; scripts/migrate_ids.py did the one-time
re-key.)

Run order
---------
    --renameFile  ->  --compressPDF  ->  --pdfToText  ->  ...

--renameFile names each PDF <sha256 of its content>.pdf, and compressing changes
the content. Renaming first means a newly downloaded book is registered in
_original_names.json under the hash of the file *as downloaded*, which is what
lets rename_files recognise the same book as a duplicate if it is downloaded
again later. Compression deliberately does NOT re-hash or rename afterwards --
the stem is the library's primary key, not a live checksum, and changing it
would break the key chain described above.

`python src/main.py --dbDoctor` reports any row whose key no longer resolves, so
a mistake here is visible rather than silent.

Safety
------
* Ghostscript writes to "<name>.pdf.gstmp" -- a suffix no other stage's *.pdf
  glob matches -- so an interrupted run can never leave a half-written file that
  --pdfToText or --buildCatalog would pick up as a book.
* The original is replaced only after the output is verified: gs exited 0, the
  file starts with %PDF, it is at least MIN_OUTPUT_BYTES, and (with PyMuPDF
  installed) it opens and reports exactly the same page count as the input. Any
  failure leaves the original untouched -- in-place means there is no second
  copy to fall back on, so verification runs before the replace, not after.
* os.replace is atomic within a filesystem: a file is either the original or the
  compressed version, never a mix.
* data/compression_log.csv records every file. A file whose current size still
  matches its logged out_bytes is skipped, which makes re-runs cheap and -- more
  importantly -- stops a file being compressed twice. Each pass re-downsamples
  the images, and that loss is permanent.

Note for --buildCatalog: it reads file sizes fresh from disk, so it reports the
savings on its next run. Cached PDF metadata is not re-probed; page counts are
unchanged by compression, but `producer` keeps showing the pre-compression value
until the probe cache is invalidated (bump PROBE_VERSION in modules/catalog.py).
"""

import os
import sys
import csv
import glob
import shutil
import subprocess
import concurrent.futures as cf
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.path import pdf_path, compression_log_path

# --- Config -----------------------------------------------------------------
PRESETS = ("screen", "ebook", "printer", "prepress")
DEFAULT_PRESET = "ebook"
TMP_SUFFIX = ".gstmp"       # deliberately not *.pdf -- other stages glob for that
MIN_OUTPUT_BYTES = 1024     # anything smaller than this is not a real PDF
GS_TIMEOUT = 1800           # seconds per file; stops one wedged gs blocking the pool
PDF_MAGIC = b"%PDF"

LOG_FIELDS = ("timestamp", "file", "status", "in_bytes", "out_bytes",
              "pct_saved", "preset", "pages")

# Statuses that mean "the file on disk is the compressed version".
_REPLACED = "compressed"

# PyMuPDF is already the extraction backend for modules/pdf_to_txt.py and the
# probe backend for modules/catalog.py. Here it is the integrity check: comparing
# page counts catches a Ghostscript run that produced a readable but truncated
# PDF, which the %PDF header check alone would happily accept.
try:
    import fitz
    HAVE_FITZ = True
except ImportError:
    fitz = None
    HAVE_FITZ = False


# --- Ghostscript discovery ---------------------------------------------------

def find_ghostscript() -> str:
    """
    Locate the Ghostscript console binary.

    Order: $GHOSTSCRIPT_PATH, then PATH, then the default Windows install
    location -- the installer does not add itself to PATH, so a plain
    shutil.which() fails on a perfectly working installation.
    """
    override = os.getenv("GHOSTSCRIPT_PATH")
    if override:
        if os.path.isfile(override):
            return override
        raise RuntimeError(f"GHOSTSCRIPT_PATH points at a missing file: {override}")

    names = ("gswin64c", "gswin32c", "gs") if os.name == "nt" else ("gs",)
    for name in names:
        found = shutil.which(name)
        if found:
            return found

    if os.name == "nt":
        candidates = []
        for root in (r"C:\Program Files\gs", r"C:\Program Files (x86)\gs"):
            candidates += glob.glob(os.path.join(root, "gs*", "bin", "gswin*c.exe"))
        if candidates:
            # Highest version directory wins.
            return sorted(candidates)[-1]

    raise RuntimeError(
        "Ghostscript not found.\n"
        "  Windows: install from https://ghostscript.com/releases/gsdnld.html\n"
        "  Linux  : apt install ghostscript\n"
        "  Or set GHOSTSCRIPT_PATH=<full path to gswin64c.exe|gs> in your .env."
    )


# --- Ledger ------------------------------------------------------------------

def load_ledger(log_path: str = compression_log_path) -> dict:
    """
    Return {filename: out_bytes} from the compression log, last entry wins.

    A missing or unreadable log is not fatal -- the worst case is that files get
    compressed a second time, which the size check below still guards against.
    """
    done = {}
    try:
        with open(log_path, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                try:
                    done[row["file"]] = int(row["out_bytes"])
                except (KeyError, TypeError, ValueError):
                    continue
    except FileNotFoundError:
        pass
    except OSError as e:
        print(f"[WARN] Could not read {log_path}: {e} -- treating every file as new.")
    return done


def _open_ledger(log_path: str):
    """Open the log for append, writing the header if the file is new."""
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    is_new = not os.path.exists(log_path) or os.path.getsize(log_path) == 0
    handle = open(log_path, "a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
    if is_new:
        writer.writeheader()
    return handle, writer


# --- Per-file work -----------------------------------------------------------

def _page_count(path: Path):
    """(pages, error). pages is None when PyMuPDF is unavailable."""
    if not HAVE_FITZ:
        return None, None
    try:
        with fitz.open(str(path)) as doc:
            if doc.needs_pass:
                return None, "password protected"
            return doc.page_count, None
    except Exception as e:
        return None, str(e)


def _looks_like_pdf(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == PDF_MAGIC
    except OSError:
        return False


def compress_one(pdf: Path, gs: str, preset: str) -> dict:
    """
    Compress one PDF in place. Returns a ledger row.

    The original is only ever replaced by a verified, strictly smaller file. On
    any other outcome the original is left exactly as it was and the status says
    why -- these are recorded rather than raised so one bad book does not stop a
    2,000-file run.
    """
    in_bytes = pdf.stat().st_size
    tmp = pdf.with_name(pdf.name + TMP_SUFFIX)
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "file": pdf.name,
        "status": "error",
        "in_bytes": in_bytes,
        "out_bytes": in_bytes,   # unchanged unless the replace actually happens
        "pct_saved": 0.0,
        "preset": preset,
        "pages": "",
    }

    try:
        src_pages, err = _page_count(pdf)
        if err:
            row["status"] = "unreadable-source"
            return row
        row["pages"] = "" if src_pages is None else src_pages

        proc = subprocess.run(
            [gs, "-sDEVICE=pdfwrite", "-dNOPAUSE", "-dBATCH", "-dQUIET",
             f"-dPDFSETTINGS=/{preset}", "-dAutoRotatePages=/None",
             "-o", str(tmp), str(pdf)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=GS_TIMEOUT,
        )

        if proc.returncode != 0 or not tmp.exists():
            row["status"] = "gs-failed"
            return row

        out_bytes = tmp.stat().st_size
        if out_bytes < MIN_OUTPUT_BYTES or not _looks_like_pdf(tmp):
            row["status"] = "bad-output"
            return row

        # Strongest check available: same number of pages in, same number out.
        if src_pages is not None:
            out_pages, out_err = _page_count(tmp)
            if out_err or out_pages != src_pages:
                row["status"] = "verify-failed"
                return row

        if out_bytes >= in_bytes:
            # Already well compressed, or mostly vector/text. Keep the original:
            # rewriting it would cost quality for no gain.
            row["status"] = "kept-original"
            return row

        try:
            os.replace(tmp, pdf)
        except OSError as e:
            # Typically the file is open in a reader; Windows refuses the replace.
            row["status"] = "locked"
            row["note"] = str(e)
            return row

        row["status"] = _REPLACED
        row["out_bytes"] = out_bytes
        row["pct_saved"] = round(100 * (1 - out_bytes / in_bytes), 1)
        return row

    except subprocess.TimeoutExpired:
        row["status"] = "timeout"
        return row
    except Exception:
        row["status"] = "error"
        return row
    finally:
        # Whatever happened, never leave a temp file behind for the next run.
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# --- Driver ------------------------------------------------------------------

def _sweep_temps(folder: Path) -> int:
    """Remove temp files left by a run that was killed mid-write."""
    removed = 0
    for stale in folder.glob("*" + TMP_SUFFIX):
        try:
            stale.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def compress_all(src=None, preset: str = DEFAULT_PRESET, jobs: int = 0,
                 dry_run: bool = False, force: bool = False,
                 log_path: str = compression_log_path) -> None:
    if preset not in PRESETS:
        raise ValueError(f"Unknown preset {preset!r}; choose one of {', '.join(PRESETS)}")

    folder = Path(src or pdf_path)
    if not folder.is_dir():
        print(f"[ERROR] Reading list folder not found: {folder}")
        print("  Set READING_LIST_PATH in your .env file.")
        sys.exit(1)

    gs = find_ghostscript()
    if jobs <= 0:
        jobs = max(1, (os.cpu_count() or 4) - 2)

    swept = _sweep_temps(folder)
    if swept:
        print(f"[INFO] Removed {swept} leftover {TMP_SUFFIX} file(s) from an interrupted run.")

    pdfs = sorted(p for p in folder.glob("*.pdf") if p.is_file())
    ledger = {} if force else load_ledger(log_path)

    todo, skipped = [], 0
    for p in pdfs:
        # Size still matching what we logged means this is the file we produced;
        # a different size means it was replaced on disk, so compress it again.
        if p.name in ledger and p.stat().st_size == ledger[p.name]:
            skipped += 1
        else:
            todo.append(p)

    total_in = sum(p.stat().st_size for p in todo)
    free = shutil.disk_usage(folder).free

    print(f"Ghostscript : {gs}")
    print(f"Source      : {folder}")
    print(f"Preset      : /{preset}   Parallel jobs: {jobs}")
    print(f"Verify      : {'page count (PyMuPDF)' if HAVE_FITZ else '%PDF header only -- pip install pymupdf for page-count verification'}")
    print(f"To process  : {len(todo)} files, {total_in / 1e9:.1f} GB "
          f"({skipped} already compressed, skipped)")
    print(f"Free space  : {free / 1e9:.1f} GB")
    print(f"Log         : {log_path}")
    print()

    if dry_run:
        for p in todo:
            print(f"  [WOULD] {p.stat().st_size / 1e6:>8.1f} MB  {p.name}")
        print(f"\n--compressDryRun: nothing written.")
        return

    if not todo:
        print("Nothing to do.")
        return

    started = datetime.now()
    counts, in_sum, out_sum, done = {}, 0, 0, 0
    handle, writer = _open_ledger(log_path)

    try:
        with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = {pool.submit(compress_one, p, gs, preset): p for p in todo}
            for future in cf.as_completed(futures):
                row = future.result()
                row.pop("note", None)
                done += 1
                counts[row["status"]] = counts.get(row["status"], 0) + 1
                in_sum += row["in_bytes"]
                out_sum += row["out_bytes"]

                # Written as each file finishes, so an interrupted run resumes
                # from where it stopped instead of re-compressing everything.
                writer.writerow(row)
                handle.flush()

                print(f"  [{done:>4}/{len(todo)}] {row['status']:<17} "
                      f"{row['in_bytes'] / 1e6:>8.1f} -> {row['out_bytes'] / 1e6:>8.1f} MB  "
                      f"{row['file'][:60]}")
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Files already finished are logged; re-run to continue.")
    finally:
        handle.close()

    elapsed = datetime.now() - started
    print()
    print(f"{done} files in {str(elapsed).split('.')[0]}")
    if in_sum:
        print(f"{in_sum / 1e9:.1f} GB -> {out_sum / 1e9:.1f} GB "
              f"({100 * (1 - out_sum / in_sum):.1f}% saved)")
    for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {status:<18} {n}")

    untouched = done - counts.get(_REPLACED, 0)
    if untouched:
        print(f"\n{untouched} file(s) were left exactly as they were "
              f"(not compressed, not damaged).")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Compress the reading list's PDFs in place.")
    ap.add_argument("--source", default=None, help="folder of PDFs (default: READING_LIST_PATH)")
    ap.add_argument("--preset", default=DEFAULT_PRESET, choices=PRESETS)
    ap.add_argument("--jobs", type=int, default=0, help="parallel Ghostscript processes (default: CPUs - 2)")
    ap.add_argument("--dryRun", action="store_true", help="list what would be done, write nothing")
    ap.add_argument("--force", action="store_true", help="ignore the log and re-compress everything")
    a = ap.parse_args()

    compress_all(src=a.source, preset=a.preset, jobs=a.jobs, dry_run=a.dryRun, force=a.force)
