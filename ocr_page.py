"""OCR a single PDF page in an isolated process.

Limits memory blast radius: if Tesseract OOMs, only this child dies.
"""
import sys

import fitz

from extractor import _ocr_page


def main():
    pdf_path, page_no, lang = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    doc = fitz.open(pdf_path)
    try:
        text = _ocr_page(doc[page_no], lang)
    finally:
        doc.close()
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
