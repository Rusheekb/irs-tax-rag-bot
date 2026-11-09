"""Split large PDFs into 8-page parts before uploading them to the knowledge base.

New AWS projects can have a low embedding limit (60 requests per minute here). A sync
of a whole 100+ page PDF goes over it and silently loses pages, so I upload the parts
and sync them one at a time.

Usage: python split_pdfs.py OUTPUT_DIR file1.pdf [file2.pdf ...]
"""
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

PAGES_PER_PART = 8


def split(pdf_path: Path, out_dir: Path):
    reader = PdfReader(pdf_path)
    total = len(reader.pages)
    for start in range(0, total, PAGES_PER_PART):
        end = min(start + PAGES_PER_PART, total)
        writer = PdfWriter()
        for page in reader.pages[start:end]:
            writer.add_page(page)
        # Page numbers in the file name show up in the app's sources.
        name = f"{pdf_path.stem}_pages_{start + 1:03d}-{end:03d}.pdf"
        with open(out_dir / name, "wb") as f:
            writer.write(f)
        print(name)


if __name__ == "__main__":
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sys.argv[2:]:
        split(Path(path), out_dir)
