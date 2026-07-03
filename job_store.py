"""Filesystem-backed job queue shared by the web app and background worker."""
import fcntl
import json
import os
import shutil
import tempfile
import time
import uuid

JOBS_ROOT = os.environ.get(
    "SCROOGE_JOBS_DIR", os.path.join(tempfile.gettempdir(), "scrooge-jobs")
)
QUEUE_DIR = os.path.join(JOBS_ROOT, "queue")
JOB_TTL_SECONDS = int(os.environ.get("SCROOGE_JOB_TTL", "3600"))


def ensure_dirs():
    os.makedirs(QUEUE_DIR, exist_ok=True)


def job_dir(job_id):
    return os.path.join(JOBS_ROOT, job_id)


def input_path(job_id):
    d = job_dir(job_id)
    for name in os.listdir(d):
        if name.startswith("input."):
            return os.path.join(d, name)
    return None


def output_path(job_id, fmt):
    return os.path.join(job_dir(job_id), f"output.{fmt}")


def write_meta(job_id, meta):
    path = os.path.join(job_dir(job_id), "meta.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    os.replace(tmp, path)


def read_meta(job_id):
    path = os.path.join(job_dir(job_id), "meta.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def update_meta(job_id, **kwargs):
    meta = read_meta(job_id)
    if meta is None:
        return
    meta.update(kwargs)
    write_meta(job_id, meta)


def cleanup_old_jobs():
    if not os.path.isdir(JOBS_ROOT):
        return
    cutoff = time.time() - JOB_TTL_SECONDS
    for name in os.listdir(JOBS_ROOT):
        if name == "queue":
            continue
        meta = read_meta(name)
        if meta and meta.get("created", 0) < cutoff:
            shutil.rmtree(job_dir(name), ignore_errors=True)
            queue_marker = os.path.join(QUEUE_DIR, name)
            if os.path.isfile(queue_marker):
                os.unlink(queue_marker)


def create_job(filename, temp_input_path, lang, is_image):
    """Move uploaded file into a job directory and enqueue it."""
    ensure_dirs()
    cleanup_old_jobs()

    job_id = uuid.uuid4().hex
    d = job_dir(job_id)
    os.makedirs(d)

    ext = os.path.splitext(filename)[1] or ".bin"
    dest = os.path.join(d, f"input{ext.lower()}")
    os.replace(temp_input_path, dest)

    write_meta(
        job_id,
        {
            "id": job_id,
            "status": "queued",
            "filename": filename,
            "lang": lang,
            "is_image": is_image,
            "created": time.time(),
            "done": 0,
            "total": 0,
            "note": "queued",
            "pages": 0,
            "ocr_pages": [],
        },
    )
    open(os.path.join(QUEUE_DIR, job_id), "w").close()
    return job_id


def acquire_next_job():
    """Return (job_id, lock_fd) for the oldest queued job, or (None, None)."""
    ensure_dirs()
    try:
        pending = os.listdir(QUEUE_DIR)
    except OSError:
        return None, None

    pending.sort(key=lambda jid: os.path.getmtime(os.path.join(QUEUE_DIR, jid)))
    for job_id in pending:
        lock_path = os.path.join(job_dir(job_id), "worker.lock")
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            continue

        queue_marker = os.path.join(QUEUE_DIR, job_id)
        if os.path.isfile(queue_marker):
            os.unlink(queue_marker)
        update_meta(job_id, status="processing", note="starting…")
        return job_id, lock_fd

    return None, None


def release_lock(job_id, lock_fd):
    fcntl.flock(lock_fd, fcntl.LOCK_UN)
    os.close(lock_fd)
    lock_path = os.path.join(job_dir(job_id), "worker.lock")
    try:
        os.unlink(lock_path)
    except OSError:
        pass
