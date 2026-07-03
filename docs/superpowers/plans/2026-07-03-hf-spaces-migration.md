# Hugging Face Spaces Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move scrooge's hosted instance from Render (512MB, OOMs on scan-heavy PDFs) to a free Hugging Face Docker Space (16GB RAM), and retire Render.

**Architecture:** No application-code changes. The Dockerfile gains a non-root UID-1000 user (HF requirement) and the env vars that previously lived in `render.yaml`. The README gains HF Space YAML frontmatter and new URLs. Deployment is a second git remote pushed to HF, which builds the Dockerfile automatically.

**Tech Stack:** Docker, Hugging Face Spaces (Docker SDK), git. App stack (Flask/gunicorn/Tesseract/PyMuPDF) unchanged.

## Global Constraints

- No paid services; HF free CPU tier only (no payment method exists).
- Container must run as UID 1000 with `HOME=/home/user` (HF Docker Spaces requirement).
- App listens on port 8000; the Space frontmatter must declare `app_port: 8000`.
- `docker build … && docker run -p 8000:8000 scrooge` must keep working for local users (spec §2).
- License identifier in frontmatter: `agpl-3.0`.
- Env defaults carried over from render.yaml: `SCROOGE_JOB_TTL=3600`, `SCROOGE_PAGE_OCR_TIMEOUT=180`.
- Some steps are **user actions** (HF account/Space creation, Render dashboard). Pause and ask the user; do not fake them.

---

### Task 1: Dockerfile — non-root user + env vars, verified locally

**Files:**
- Modify: `Dockerfile` (whole file, currently 18 lines)
- Test: manual `docker build` / `docker run` + `curl` (no pytest suite exists in this repo)

**Interfaces:**
- Produces: an image that any Docker host (HF, local) can run as-is; jobs dir at `/home/user/jobs` via `SCROOGE_JOBS_DIR` (already read by `job_store.py:10`).

- [ ] **Step 1: Replace the Dockerfile contents**

```dockerfile
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

RUN chmod +x start.sh && useradd -m -u 1000 user

USER user
ENV HOME=/home/user
ENV PORT=8000
ENV SCROOGE_JOBS_DIR=/home/user/jobs
ENV SCROOGE_JOB_TTL=3600
ENV SCROOGE_PAGE_OCR_TIMEOUT=180
EXPOSE 8000
CMD ["./start.sh"]
```

Notes for the implementer: `start.sh` runs `mkdir -p "$JOBS_DIR/queue"`, which now targets `/home/user/jobs` — writable by `user` because `useradd -m` created the home dir. Nothing writes to `/app`, so no `chown` is needed (spec §2). Uploads use `tempfile.mkstemp` → `/tmp`, which is world-writable.

- [ ] **Step 2: Build the image**

Run: `docker build -t scrooge /Users/slee/scrooge`
Expected: ends with `naming to docker.io/library/scrooge` (exit 0). If Docker Desktop isn't running, ask the user to start it.

- [ ] **Step 3: Run the container and verify a full job end-to-end**

```bash
docker run -d --rm --name scrooge-test -p 8000:8000 scrooge
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/      # expect: 200
# Make a tiny one-page PDF with a text layer and run it through the job API:
python3 -c "import fitz; d=fitz.open(); p=d.new_page(); p.insert_text((72,72),'Hello scrooge migration test, this line is long enough to pass the text-layer threshold.'); d.save('/tmp/mig-test.pdf')"
JOB=$(curl -s -F file=@/tmp/mig-test.pdf -F lang=eng http://127.0.0.1:8000/api/jobs | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
sleep 3
curl -s http://127.0.0.1:8000/api/jobs/$JOB | python3 -m json.tool
```

Expected: final JSON has `"status": "done"` and a non-empty `preview.txt` containing "Hello scrooge migration test". (The `python3 -c` PDF generator needs pymupdf on the host; if missing, run it with `/Users/slee/scrooge/.venv/bin/python` or any interpreter that has `fitz`.)

- [ ] **Step 4: Stop the container**

Run: `docker stop scrooge-test`
Expected: prints `scrooge-test`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile
git commit -m "Run container as UID-1000 user with env defaults for HF Spaces"
```

---

### Task 2: README frontmatter + hosting rewrite, delete render.yaml

**Files:**
- Modify: `README.md` (frontmatter at top; lines 5–7 online-URL block; lines 87–92 "Version 1" section; lines 128–135 "Host your own copy" section)
- Delete: `render.yaml`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: README that HF parses as Space config (`sdk: docker`, `app_port: 8000`). The literal placeholder `HF-USERNAME` appears in URLs and is replaced in Task 3 once the user's actual HF username is known.

- [ ] **Step 1: Add YAML frontmatter at the very top of README.md** (above the existing `<img …>` line):

```markdown
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
```

- [ ] **Step 2: Replace the online-URL block (current lines 5–7)**

Old:

```markdown
**▶ Use it online: https://scrooge-4cx7.onrender.com/** — no install needed.
(Free-tier hosting: the site sleeps when idle, so the first visit may take
~30–60 s to wake up.)
```

New:

```markdown
**▶ Use it online: https://HF-USERNAME-scrooge.hf.space/** — no install needed.
(Free-tier hosting: the Space sleeps after ~48 h without visitors, so a
first visit after a quiet spell may take a minute to wake up.)
```

- [ ] **Step 3: Update the "Version 1: Use it online (hosted)" section (current lines 87–92)**

Old first sentence:

```markdown
Just open **https://scrooge-4cx7.onrender.com/**. Note that uploaded files
```

New first sentence:

```markdown
Just open **https://HF-USERNAME-scrooge.hf.space/**. Note that uploaded files
```

(Rest of the paragraph unchanged.)

- [ ] **Step 4: Rewrite the "Host your own copy" section (current lines 128–135)**

Old:

```markdown
GitHub Pages **cannot** host this (it serves static files only — no Python,
no Tesseract), and Vercel's serverless runtime doesn't ship the Tesseract
binary. Use a Docker-friendly host instead; the included `Dockerfile` and
`render.yaml` work as-is on **Render** (that's what powers the official
instance above), and the `Dockerfile` alone works on **Railway** or
**Fly.io** (`fly launch`).
```

New:

```markdown
GitHub Pages **cannot** host this (it serves static files only — no Python,
no Tesseract), and Vercel's serverless runtime doesn't ship the Tesseract
binary. Use a Docker-friendly host instead. The official instance runs as a
**Hugging Face Docker Space** (free tier: 16 GB RAM — enough to OCR large
scanned PDFs): create a new Space with the *Docker* SDK, then push this
repo to it; the YAML block at the top of this README is the Space config.
The `Dockerfile` alone also works on **Render**, **Railway**, or **Fly.io**
(`fly launch`), but note Render's free tier (512 MB RAM) is OOM-killed by
scan-heavy PDFs — that's why the official instance moved.
```

- [ ] **Step 5: Delete render.yaml**

Run: `git rm render.yaml`
Expected: `rm 'render.yaml'`

- [ ] **Step 6: Sanity-check the frontmatter parses as YAML**

Run: `python3 -c "import yaml,io; t=open('/Users/slee/scrooge/README.md').read(); print(yaml.safe_load(t.split('---')[1]))"`
Expected: a dict printing `{'title': 'Scrooge Lab Tools', … 'app_port': 8000, …}`. (If `yaml` isn't installed on the host python, use `/Users/slee/scrooge/.venv/bin/python` — pymupdf4llm's deps don't include yaml either; in that case `pip install pyyaml` into the venv or just eyeball the block against Step 1.)

- [ ] **Step 7: Commit**

```bash
git add README.md render.yaml
git commit -m "Point README at Hugging Face Space, add Space config, drop render.yaml"
```

---

### Task 3: Create the Space, push, fill in the real URL

**Files:**
- Modify: `README.md` (replace `HF-USERNAME` placeholder, 2 occurrences)

**Interfaces:**
- Consumes: `HF-USERNAME` placeholder from Task 2.
- Produces: live Space at `https://HF-USERNAME-scrooge.hf.space/`; git remote named `hf`.

- [ ] **Step 1: USER ACTION — ask the user to do the following and report back their HF username:**
  1. Create a free account at https://huggingface.co/join (if they don't have one).
  2. Create a new Space: https://huggingface.co/new-space — name `scrooge`, License AGPL-3.0, SDK **Docker** (blank template), hardware **CPU basic (free)**, visibility Public.
  3. Create a write-scoped access token at https://huggingface.co/settings/tokens (needed as the git password when pushing).

- [ ] **Step 2: Replace the placeholder with the real username (2 occurrences)**

Run (substituting the reported username for `USERNAME`):

```bash
sed -i '' 's/HF-USERNAME/USERNAME/g' /Users/slee/scrooge/README.md
grep -c 'USERNAME-scrooge.hf.space' /Users/slee/scrooge/README.md
```

Expected: grep prints `2`. Note the URL uses a dash between username and space name: `https://USERNAME-scrooge.hf.space/`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Fill in the live Space URL"
```

- [ ] **Step 4: Add the HF remote and push**

```bash
git remote add hf https://huggingface.co/spaces/USERNAME/scrooge
git push --force hf main
```

Expected: push succeeds (HF pre-creates an initial commit in new Spaces, hence `--force`). Git will prompt for credentials: username = HF username, password = the write token from Step 1. If the environment can't do interactive git auth, ask the user to run the push themselves with `! git push --force hf main`.

- [ ] **Step 5: Watch the build**

The Space builds automatically after the push. Ask the user to open `https://huggingface.co/spaces/USERNAME/scrooge` and wait for status **Running** (build takes a few minutes), or poll:

Run: `curl -s -o /dev/null -w "%{http_code}\n" https://USERNAME-scrooge.hf.space/`
Expected: `200` once running (may be `404`/`503` while building; retry every ~30 s).

---

### Task 4: Acceptance verification on the live Space, retire Render

**Files:** none (verification + user account actions)

**Interfaces:**
- Consumes: live Space URL from Task 3.

- [ ] **Step 1: Smoke-test the live Space with a small generated PDF**

```bash
python3 -c "import fitz; d=fitz.open(); p=d.new_page(); p.insert_text((72,72),'Hello scrooge migration test, this line is long enough to pass the text-layer threshold.'); d.save('/tmp/mig-test.pdf')"
JOB=$(curl -s -F file=@/tmp/mig-test.pdf -F lang=eng https://USERNAME-scrooge.hf.space/api/jobs | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
sleep 5
curl -s https://USERNAME-scrooge.hf.space/api/jobs/$JOB | python3 -m json.tool
```

Expected: `"status": "done"`, preview contains the test sentence.

- [ ] **Step 2: The real acceptance test — the 77MB PDF (spec §6)**

Ask the user for the path to the 77MB PDF that OOM'd on Render (and, if handy, a ~5MB scanned one). Then:

```bash
JOB=$(curl -s -F file=@"PATH-TO-77MB.pdf" -F lang=eng https://USERNAME-scrooge.hf.space/api/jobs | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
watch -n 10 "curl -s https://USERNAME-scrooge.hf.space/api/jobs/$JOB | python3 -c 'import sys,json; m=json.load(sys.stdin); print(m[\"status\"], m[\"done\"], \"/\", m[\"total\"], m[\"note\"])'"
```

(Or poll with a plain loop if `watch` is unavailable: `for i in $(seq 1 200); do curl -s …; sleep 15; done`.) OCR pages take up to ~3 min each (`SCROOGE_PAGE_OCR_TIMEOUT=180`), so a big scanned document legitimately takes a while — progress advancing page by page is the success signal, `status: error` or a dead Space is failure.

Expected: `status` reaches `done`; then download and spot-check:

```bash
curl -s -o /tmp/result.md "https://USERNAME-scrooge.hf.space/api/jobs/$JOB/download?fmt=md"
head -c 2000 /tmp/result.md
```

- [ ] **Step 3: Verify /plots still loads**

Run: `curl -s -o /dev/null -w "%{http_code}\n" https://USERNAME-scrooge.hf.space/plots`
Expected: `200`.

- [ ] **Step 4: USER ACTION — retire Render**

Ask the user to suspend or delete the `scrooge` service in the Render dashboard (https://dashboard.render.com). Only after Step 2 passed.

- [ ] **Step 5: Push final state to GitHub**

```bash
git push origin main
```

Expected: GitHub repo now shows the HF URLs and no render.yaml.
