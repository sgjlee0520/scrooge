"""PDF text extraction with smart per-page routing.

Pages with an embedded text layer are extracted directly (fast, lossless).
Pages without one (scans) are rendered to images and OCR'd with Tesseract.
"""
import io
import re

import fitz  # PyMuPDF
import pymupdf4llm
import pytesseract
from PIL import Image

OCR_DPI = 300
# Pages with fewer extractable characters than this are treated as scanned.
MIN_CHARS_FOR_TEXT_PAGE = 30


def available_languages():
    langs = [l for l in pytesseract.get_languages() if l not in ("osd", "snum")]
    return sorted(langs)


def _ocr_page(page, lang):
    pix = page.get_pixmap(dpi=OCR_DPI)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    return pytesseract.image_to_string(img, lang=lang)


def _ocr_text_to_markdown(text):
    """Light-touch markdown for OCR output: keep paragraphs, unwrap hard
    line breaks inside them."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    out = []
    for p in paragraphs:
        lines = [l.strip() for l in p.splitlines() if l.strip()]
        if not lines:
            continue
        out.append(" ".join(lines))
    return "\n\n".join(out)


def extract(pdf_path, lang="eng", progress_cb=None):
    """Returns {"txt": str, "md": str, "pages": int, "ocr_pages": [int]}.

    progress_cb(done, total, note) is called after each page.
    """
    doc = fitz.open(pdf_path)
    total = doc.page_count

    is_text_page = []
    for page in doc:
        chars = len(page.get_text("text").strip())
        is_text_page.append(chars >= MIN_CHARS_FOR_TEXT_PAGE)

    # Markdown for text-layer pages comes from pymupdf4llm, which preserves
    # headings, lists and tables; chunked so we can re-interleave by page.
    text_page_indices = [i for i, t in enumerate(is_text_page) if t]
    md_by_page = {}
    if text_page_indices:
        chunks = pymupdf4llm.to_markdown(
            doc, pages=text_page_indices, page_chunks=True, show_progress=False
        )
        for idx, chunk in zip(text_page_indices, chunks):
            md_by_page[idx] = chunk["text"].strip()

    txt_parts, md_parts, ocr_pages = [], [], []
    for i, page in enumerate(doc):
        if is_text_page[i]:
            txt_parts.append(page.get_text("text").strip())
            md_parts.append(md_by_page.get(i, ""))
            note = f"extracted text layer from page {i + 1}"
        else:
            ocr_pages.append(i + 1)
            raw = _ocr_page(page, lang)
            txt_parts.append(raw.strip())
            md_parts.append(_ocr_text_to_markdown(raw))
            note = f"OCR'd page {i + 1}"
        if progress_cb:
            progress_cb(i + 1, total, note)

    doc.close()
    return {
        "txt": "\n\n".join(p for p in txt_parts if p),
        "md": "\n\n".join(p for p in md_parts if p),
        "pages": total,
        "ocr_pages": ocr_pages,
    }
