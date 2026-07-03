"""PDF text extraction with smart per-page routing.

Pages with an embedded text layer are extracted directly (fast, lossless).
Pages without one (scans) are rendered to images and OCR'd with Tesseract.
"""
import gc
import os
import re
import subprocess
import sys
import tempfile

import fitz  # PyMuPDF
import pymupdf4llm
import pytesseract
from PIL import Image

OCR_DPI = 300
# Cap rendered long edge so a single page cannot allocate hundreds of MB.
MAX_OCR_LONG_EDGE = 2400
MIN_CHARS_FOR_TEXT_PAGE = 30
PAGE_OCR_TIMEOUT = int(os.environ.get("SCROOGE_PAGE_OCR_TIMEOUT", "180"))


def available_languages():
    langs = [l for l in pytesseract.get_languages() if l not in ("osd", "snum")]
    return sorted(langs)


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")


def _ocr_render_dpi(page):
    long_in = max(page.rect.width, page.rect.height) / 72.0
    if long_in <= 0:
        return OCR_DPI
    return min(OCR_DPI, max(72, int(MAX_OCR_LONG_EDGE / long_in)))


def _ocr_page(page, lang):
    pix = page.get_pixmap(dpi=_ocr_render_dpi(page), alpha=False)
    try:
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return pytesseract.image_to_string(img, lang=lang)
    finally:
        del pix


def _ocr_page_subprocess(pdf_path, page_index, lang):
    result = subprocess.run(
        [sys.executable, os.path.join(os.path.dirname(__file__), "ocr_page.py"),
         pdf_path, str(page_index), lang],
        capture_output=True,
        text=True,
        timeout=PAGE_OCR_TIMEOUT,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "OCR subprocess failed").strip()
        raise RuntimeError(f"OCR failed on page {page_index + 1}: {err}")
    return result.stdout


def _ocr_text_to_markdown(text):
    paragraphs = re.split(r"\n\s*\n", text.strip())
    out = []
    for p in paragraphs:
        lines = [l.strip() for l in p.splitlines() if l.strip()]
        if not lines:
            continue
        out.append(" ".join(lines))
    return "\n\n".join(out)


def _append_page(txt_f, md_f, txt, md, first_page):
    if not txt and not md:
        return first_page
    if not first_page:
        txt_f.write("\n\n")
        md_f.write("\n\n")
    txt_f.write(txt)
    md_f.write(md)
    txt_f.flush()
    md_f.flush()
    return False


def extract_pdf_to_files(pdf_path, txt_path, md_path, lang="eng", progress_cb=None):
    """Process one page at a time; append results to disk (bounded RAM)."""
    ocr_pages = []
    doc = fitz.open(pdf_path)
    total = doc.page_count
    first_page = True

    with open(txt_path, "w", encoding="utf-8") as txt_f, open(
        md_path, "w", encoding="utf-8"
    ) as md_f:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if len(text) >= MIN_CHARS_FOR_TEXT_PAGE:
                chunks = pymupdf4llm.to_markdown(
                    doc, pages=[i], page_chunks=True, show_progress=False
                )
                md = chunks[0]["text"].strip() if chunks else ""
                first_page = _append_page(txt_f, md_f, text, md, first_page)
                note = f"extracted text layer from page {i + 1}"
            else:
                ocr_pages.append(i + 1)
                raw = _ocr_page_subprocess(pdf_path, i, lang).strip()
                md = _ocr_text_to_markdown(raw)
                first_page = _append_page(txt_f, md_f, raw, md, first_page)
                note = f"OCR'd page {i + 1}"
                gc.collect()

            if progress_cb:
                progress_cb(i + 1, total, note)

    doc.close()
    return {"pages": total, "ocr_pages": ocr_pages}


def extract_image_to_files(image_path, txt_path, md_path, lang="eng", progress_cb=None):
    """OCR a single image; write results to disk."""
    img = Image.open(image_path)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    raw = pytesseract.image_to_string(img, lang=lang).strip()
    md = _ocr_text_to_markdown(raw)
    with open(txt_path, "w", encoding="utf-8") as txt_f, open(
        md_path, "w", encoding="utf-8"
    ) as md_f:
        txt_f.write(raw)
        md_f.write(md)
    if progress_cb:
        progress_cb(1, 1, "OCR'd image")
    return {"pages": 1, "ocr_pages": [1]}


def extract(pdf_path, lang="eng", progress_cb=None):
    """In-memory API for MCP / scripts. Uses disk streaming internally."""
    with tempfile.TemporaryDirectory() as td:
        txt_path = os.path.join(td, "output.txt")
        md_path = os.path.join(td, "output.md")
        meta = extract_pdf_to_files(pdf_path, txt_path, md_path, lang, progress_cb)
        with open(txt_path, encoding="utf-8") as f:
            txt = f.read()
        with open(md_path, encoding="utf-8") as f:
            md = f.read()
        return {"txt": txt, "md": md, **meta}


def extract_image(image_path, lang="eng", progress_cb=None):
    with tempfile.TemporaryDirectory() as td:
        txt_path = os.path.join(td, "output.txt")
        md_path = os.path.join(td, "output.md")
        meta = extract_image_to_files(image_path, txt_path, md_path, lang, progress_cb)
        with open(txt_path, encoding="utf-8") as f:
            txt = f.read()
        with open(md_path, encoding="utf-8") as f:
            md = f.read()
        return {"txt": txt, "md": md, **meta}
