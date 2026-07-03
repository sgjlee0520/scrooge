# Migrate scrooge hosting from Render to Hugging Face Spaces

**Date:** 2026-07-03
**Status:** Approved

## Problem

The hosted instance runs on Render's free tier (512MB RAM). At OCR time four
processes are resident — gunicorn/Flask (~150MB), worker.py (~120MB), the
ocr_page.py subprocess (~100MB+), and Tesseract itself (~100–300MB per
300-DPI page, more for `kor`) — so the container is OOM-killed on scan-heavy
PDFs. Even a 5MB scanned PDF can fail, because per-page memory depends on
page dimensions × DPI, not file size. Constraint: no paid hosting.

## Decision

Migrate the hosted instance to a **Hugging Face Docker Space** (free tier:
16GB RAM, 2 vCPU, no payment method required) and **retire the Render
service**. No memory-diet changes to the OCR pipeline — 16GB removes the
constraint outright.

Alternatives rejected:

- **Slim the pipeline to fit 512MB** — plausibly fixes small files, but a
  77MB scan-heavy PDF stays at risk; 512MB total is genuinely tight.
- **Oracle Cloud always-free VM** — 24GB RAM but requires a payment card for
  identity verification and ongoing server administration.
- **Google Cloud Run free quota** — requires a billing account; overruns
  would charge.

## Changes

### 1. Application code

None. Flask app, worker, filesystem job queue, per-page OCR pipeline,
templates, and MCP server are untouched.

### 2. Dockerfile

HF runs Docker Spaces as a non-root user (UID 1000), so writes to
`/var/scrooge/jobs` and `/app` would fail. Changes:

- Create user `user` with UID 1000; set `ENV HOME=/home/user` and
  `USER user`. No `chown` of `/app` is needed: the app only writes to
  `SCROOGE_JOBS_DIR` and `/tmp`.
- `ENV SCROOGE_JOBS_DIR=/home/user/jobs` (read by `job_store.py`).
- Move the env vars that currently live only in `render.yaml` into the
  Dockerfile: `SCROOGE_JOB_TTL=3600`, `SCROOGE_PAGE_OCR_TIMEOUT=180`.
- Result must still work with plain `docker run` for local users.

### 3. README.md

- Add HF Space YAML frontmatter at the very top: `title`, `emoji`,
  `colorFrom`/`colorTo`, `sdk: docker`, `app_port: 8000`, `pinned: false`,
  `license: agpl-3.0`. (GitHub renders this as a small table — accepted
  trade-off, standard for repos mirrored to Spaces.)
- Replace the Render URL with the new Space URL.
- Update the sleep note: free Spaces sleep after ~48h idle (vs Render's
  ~15min).
- Rewrite "Host your own copy" for HF Spaces; mention Render/Railway/Fly
  only as "also works" alternatives.

### 4. Retire Render

- Delete `render.yaml` from the repo.
- The user suspends/deletes the service in the Render dashboard (account
  action, done by the user).

### 5. Deployment flow

1. User creates a free HF account and an empty **Docker** Space named
   `scrooge`.
2. Add the Space as a second git remote; `git push hf main` deploys (HF
   builds the Dockerfile automatically). GitHub stays the primary repo.

### 6. Verification / acceptance

On the live Space:

- Upload the real 77MB PDF; job progresses page-by-page to `done`;
  download the `.md`.
- Upload a ~5MB scanned PDF; same.
- Confirm the `/plots` digitizer still works.
- Confirm `docker build && docker run -p 8000:8000 scrooge` still works
  locally with the modified Dockerfile.

## Error handling

Unchanged: per-page OCR timeout (`SCROOGE_PAGE_OCR_TIMEOUT`) and job TTL
cleanup already exist and keep working on HF. The 100MB Flask upload cap
(`MAX_CONTENT_LENGTH`) stays and covers the 77MB use case.
