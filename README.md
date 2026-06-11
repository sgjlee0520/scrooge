# Lab Tools — PDF → Text and Plot → Data

Two utilities for turning pixels into token-cheap, computation-ready text
(see [TOKEN_ECONOMICS.md](TOKEN_ECONOMICS.md) for the cost argument):

1. **PDF → Text** (`/`) — converts uploaded PDFs to plain text or Markdown,
   downloadable as `.txt` or `.md`.
2. **Plot → Data** (`/plots`) — digitizes images of simple plots into
   (x, y) data series, downloadable as `.csv`, `.json`, `.md`, or a
   matplotlib `.py` script.

## How PDF → Text works

Each page is routed to the best extraction method:

- **Pages with an embedded text layer** → extracted directly with PyMuPDF
  (lossless, fast). Markdown conversion via `pymupdf4llm`, which preserves
  headings, lists, and tables.
- **Scanned/image pages** → rendered at 300 DPI and OCR'd with Tesseract.

Mixed documents are handled per page, so a PDF with some scanned pages and
some digital pages comes out right.

## How Plot → Data works

The user clicks two known points per axis to calibrate the pixel→data
mapping (log axes supported), then clicks each curve/point series to sample
its color. Pixels matching each color are masked and collapsed into points —
median row per column for lines, blob centroids for scatter. Extraction is
shape-agnostic: lines, sinusoids, parabolas, any y = f(x) curve.

## MCP server (use the tools from Claude)

`mcp_server.py` exposes `pdf_to_text`, `digitize_plot`, and
`list_ocr_languages` over stdio, so Claude Code / Claude Desktop can read
scanned PDFs and plot images as cheap text instead of vision tokens:

```sh
claude mcp add lab-tools -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
```

> **Caveat:** the web UI's click-to-calibrate doesn't exist over MCP, so
> Claude has to be told the calibration pixel coordinates — or look at the
> image once to find the axis ticks itself, which is still a one-time cost
> versus re-reading the image on every conversation turn.

## Requirements

- Python 3.10+
- Tesseract (`brew install tesseract`)
- Extra OCR languages: drop `<lang>.traineddata` files into
  `/opt/homebrew/share/tessdata/` (from
  https://github.com/tesseract-ocr/tessdata_fast). `eng` and `kor` are
  already installed on this machine.

## Run

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open http://127.0.0.1:5050.

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/jobs` | POST | Upload (`file`, `lang` form fields); returns job `id` |
| `/api/jobs/<id>` | GET | Progress / result preview |
| `/api/jobs/<id>/download?fmt=txt\|md` | GET | Download result |

## License

AGPL-3.0 (see [LICENSE](LICENSE)). This project depends on PyMuPDF, which
is AGPL-licensed; if you run a modified version of this app as a network
service, the AGPL requires you to offer your users its source code.

## Notes for deployment

The job store is in-memory and the server runs Flask's dev server — fine
locally. To put this on the internet: run under gunicorn with **one** worker
(or move jobs to Redis/RQ), add a reverse proxy, and consider rate limiting,
since OCR is CPU-heavy.
