"""Background worker: processes queued PDF/image extraction jobs."""
import os
import sys
import time

import extractor
import job_store


def process_job(job_id):
    meta = job_store.read_meta(job_id)
    if meta is None:
        return

    src = job_store.input_path(job_id)
    if not src:
        job_store.update_meta(job_id, status="error", error="Missing input file.")
        return

    txt_path = job_store.output_path(job_id, "txt")
    md_path = job_store.output_path(job_id, "md")

    def progress(done, total, note):
        job_store.update_meta(job_id, done=done, total=total, note=note)

    try:
        if meta["is_image"]:
            result = extractor.extract_image_to_files(
                src, txt_path, md_path, meta["lang"], progress
            )
        else:
            result = extractor.extract_pdf_to_files(
                src, txt_path, md_path, meta["lang"], progress
            )
        job_store.update_meta(
            job_id, status="done", note="complete", pages=result["pages"],
            ocr_pages=result["ocr_pages"],
        )
    except Exception as e:
        job_store.update_meta(job_id, status="error", error=str(e))
    finally:
        try:
            os.unlink(src)
        except OSError:
            pass


def run_once():
    job_id, lock_fd = job_store.acquire_next_job()
    if not job_id:
        return False
    try:
        process_job(job_id)
    finally:
        job_store.release_lock(job_id, lock_fd)
    return True


def main():
    job_store.ensure_dirs()
    poll = float(os.environ.get("SCROOGE_WORKER_POLL", "1"))
    print(f"worker: watching {job_store.JOBS_ROOT}", flush=True)
    while True:
        if not run_once():
            time.sleep(poll)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
