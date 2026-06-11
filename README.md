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

## Version 1: Run it locally (private)

Your files never leave your machine — use this for sensitive documents.

**Prerequisites:** Python 3.10+ and Tesseract:

```sh
# macOS                          # Debian/Ubuntu
brew install tesseract           sudo apt install tesseract-ocr
```

For OCR languages beyond English, drop `<lang>.traineddata` files from
[tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) into your
tessdata directory (`/opt/homebrew/share/tessdata/` on macOS,
`/usr/share/tesseract-ocr/*/tessdata/` on Linux), or
`brew install tesseract-lang` / `apt install tesseract-ocr-kor` etc.

**Install and run:**

```sh
git clone https://github.com/sgjlee0520/scrooge
cd scrooge
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Then open http://127.0.0.1:5050.

**Or with Docker** (English + Korean OCR included):

```sh
docker build -t scrooge . && docker run -p 8000:8000 scrooge
```

## Version 2: Host it online

GitHub Pages **cannot** host this (it serves static files only — no Python,
no Tesseract), and Vercel's serverless runtime doesn't ship the Tesseract
binary. Use a Docker-friendly host instead; the included `Dockerfile` works
as-is on **Render**, **Railway**, or **Fly.io**:

- **Render / Railway:** create a new web service, connect this repo — the
  `Dockerfile` is detected automatically. Both have free tiers (which sleep
  when idle; OCR is CPU-heavy, so expect slow cold starts there).
- **Fly.io:** `fly launch` in the repo root.

**Privacy note for the hosted version:** uploaded files transit your server
(they're written to a temp file and deleted after processing, with results
held in memory). Say so in your site's footer, and point privacy-sensitive
users at the local version.

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

## Production hardening notes

The `Dockerfile` already runs gunicorn with a single worker (required: the
job store is in-process memory — moving to more workers means moving jobs
to Redis/RQ). Before serious public traffic, also add per-IP rate limiting
(OCR is CPU-heavy, so abuse melts the server) and periodic cleanup of old
jobs from the in-memory store.
