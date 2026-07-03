---
title: Scrooge Lab Tools
emoji: 📄
colorFrom: yellow
colorTo: gray
sdk: docker
app_port: 8000
pinned: false
license: agpl-3.0
---

<img width="1408" height="768" alt="Gemini_Generated_Image_2uwf3z2uwf3z2uwf" src="https://github.com/user-attachments/assets/a8cbbee0-1fc8-45ef-ad09-5285886af967" />

# Lab Tools — PDF → Text and Plot → Data

**▶ Use it online: https://sgjlee0520-scrooge.hf.space/** — no install needed.
(Free-tier hosting: the Space sleeps after ~48 h without visitors, so a
first visit after a quiet spell may take a minute to wake up.)

Two utilities for turning pixels into token-cheap, computation-ready text
(see [TOKEN_ECONOMICS.md](TOKEN_ECONOMICS.md) for the cost argument):

1. **PDF / Image → Text** (`/`) — converts uploaded PDFs *and* images
   (PNG/JPEG/TIFF/BMP/WebP) to plain text or Markdown, downloadable as
   `.txt` or `.md`.
2. **Plot → Data** (`/plots`) — digitizes images of simple plots into
   (x, y) data series, downloadable as `.csv`, `.json`, `.md`, or a
   matplotlib `.py` script.

## How PDF / Image → Text works

Each PDF page is routed to the best extraction method:

- **Pages with an embedded text layer** → extracted directly with PyMuPDF
  (lossless, fast). Markdown conversion via `pymupdf4llm`, which preserves
  headings, lists, and tables.
- **Scanned/image pages** → rendered at 300 DPI and OCR'd with Tesseract.

Mixed documents are handled per page, so a PDF with some scanned pages and
some digital pages comes out right. Uploaded images (PNG/JPEG/TIFF/BMP/WebP)
go straight to Tesseract OCR.

## How Plot → Data works

The user clicks two known points per axis to calibrate the pixel→data
mapping (log axes supported), then clicks each curve/point series to sample
its color. Pixels matching each color are masked and collapsed into points —
median row per column for lines, blob centroids for scatter. Extraction is
shape-agnostic: lines, sinusoids, parabolas, any y = f(x) curve.

## MCP server (use the tools from Claude, ChatGPT, or Gemini)

`mcp_server.py` exposes `pdf_to_text`, `image_to_text`, `digitize_plot`, and
`list_ocr_languages` over MCP, so AI agents can read scanned PDFs, images,
and plot figures as cheap text instead of vision tokens. Set up the local
install first (Version 2 above), then register it with your client:

**Claude Code / Claude Desktop:**

```sh
claude mcp add lab-tools -- "$PWD/.venv/bin/python" "$PWD/mcp_server.py"
```

**Codex CLI (ChatGPT):** add to `~/.codex/config.toml`:

```toml
[mcp_servers.lab-tools]
command = "/absolute/path/to/scrooge/.venv/bin/python"
args = ["/absolute/path/to/scrooge/mcp_server.py"]
```

**Gemini CLI:** add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "lab-tools": {
      "command": "/absolute/path/to/scrooge/.venv/bin/python",
      "args": ["/absolute/path/to/scrooge/mcp_server.py"]
    }
  }
}
```

**ChatGPT app (connectors):** ChatGPT only accepts *remote* MCP servers.
Run `mcp_server.py --http` (serves streamable HTTP at
`http://127.0.0.1:8000/mcp`), expose it via a public HTTPS URL (e.g.
`ngrok http 8000`), then add it under ChatGPT → Settings → Apps &
Connectors (requires developer mode). Note the tools take *local file
paths*, so they only make sense when the server runs on the machine that
has your files.

> **Caveat:** the web UI's click-to-calibrate doesn't exist over MCP, so
> Claude has to be told the calibration pixel coordinates — or look at the
> image once to find the axis ticks itself, which is still a one-time cost
> versus re-reading the image on every conversation turn.

## Version 1: Use it online (hosted)

Just open **https://sgjlee0520-scrooge.hf.space/**. Note that uploaded files
transit the server (written to a temp file, deleted after processing) — for
sensitive documents, use the local version below.

## Version 2: Run it locally (private)

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

## Host your own copy

GitHub Pages **cannot** host this (it serves static files only — no Python,
no Tesseract), and Vercel's serverless runtime doesn't ship the Tesseract
binary. Use a Docker-friendly host instead. The official instance runs as a
**Hugging Face Docker Space** (free tier: 16 GB RAM — enough to OCR large
scanned PDFs): create a new Space with the *Docker* SDK, then push this
repo to it; the YAML block at the top of this README is the Space config.
The `Dockerfile` alone also works on **Render**, **Railway**, or **Fly.io**
(`fly launch`), but note Render's free tier (512 MB RAM) is OOM-killed by
scan-heavy PDFs — that's why the official instance moved.

**Privacy note for hosts:** uploaded files transit your server (written to
a temp file, deleted after processing, results held in memory). Say so on
your instance, and point privacy-sensitive users at the local version.

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
