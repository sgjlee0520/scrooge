import json
import os
import tempfile
import threading
import uuid

from flask import Flask, jsonify, render_template, request, Response
from PIL import Image

import extractor
import plot_digitizer

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB

# In-memory job store. Fine for a single-process local app; swap for
# Redis/RQ if this ever runs multi-worker in production.
jobs = {}
jobs_lock = threading.Lock()


def _run_job(job_id, path, lang, is_image):
    def progress(done, total, note):
        with jobs_lock:
            jobs[job_id].update(done=done, total=total, note=note)

    try:
        fn = extractor.extract_image if is_image else extractor.extract
        result = fn(path, lang=lang, progress_cb=progress)
        with jobs_lock:
            jobs[job_id].update(status="done", result=result)
    except Exception as e:
        with jobs_lock:
            jobs[job_id].update(status="error", error=str(e))
    finally:
        os.unlink(path)


@app.get("/")
def index():
    return render_template("index.html", languages=extractor.available_languages())


@app.post("/api/jobs")
def create_job():
    file = request.files.get("file")
    name = (file.filename or "").lower() if file else ""
    is_image = name.endswith(extractor.IMAGE_EXTS)
    if not file or not (name.endswith(".pdf") or is_image):
        return jsonify(error="Please upload a PDF or image (PNG/JPEG) file."), 400
    lang = request.form.get("lang", "eng")
    if lang not in extractor.available_languages():
        return jsonify(error=f"OCR language '{lang}' is not installed."), 400

    suffix = os.path.splitext(name)[1] or ".bin"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        file.save(f)

    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "status": "processing",
            "filename": file.filename,
            "done": 0,
            "total": 0,
            "note": "starting…",
        }
    threading.Thread(target=_run_job, args=(job_id, path, lang, is_image), daemon=True).start()
    return jsonify(id=job_id)


@app.get("/api/jobs/<job_id>")
def job_status(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify(error="Unknown job."), 404
        payload = {k: v for k, v in job.items() if k != "result"}
        if job["status"] == "done":
            payload["preview"] = {
                "txt": job["result"]["txt"][:20000],
                "md": job["result"]["md"][:20000],
            }
            payload["pages"] = job["result"]["pages"]
            payload["ocr_pages"] = job["result"]["ocr_pages"]
    return jsonify(payload)


@app.get("/api/jobs/<job_id>/download")
def download(job_id):
    fmt = request.args.get("fmt", "txt")
    if fmt not in ("txt", "md"):
        return jsonify(error="fmt must be txt or md"), 400
    with jobs_lock:
        job = jobs.get(job_id)
        if not job or job["status"] != "done":
            return jsonify(error="Job not finished."), 404
        content = job["result"][fmt]
        base = os.path.splitext(job["filename"])[0]
    return Response(
        content,
        mimetype="text/markdown" if fmt == "md" else "text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="{base}.{fmt}"'
        },
    )


@app.get("/plots")
def plots():
    return render_template("plots.html")


@app.post("/api/plot-digitize")
def plot_digitize():
    file = request.files.get("file")
    if not file:
        return jsonify(error="Please upload an image."), 400
    try:
        params = json.loads(request.form["params"])
        img = Image.open(file.stream)
        series = plot_digitizer.digitize(
            img,
            params["calibration"],
            params["colors"],
            mode=params.get("mode", "line"),
            tolerance=float(params.get("tolerance", 40)),
            max_points=int(params.get("max_points", 60)),
            x_log=bool(params.get("x_log", False)),
            y_log=bool(params.get("y_log", False)),
        )
        return jsonify(series=series)
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        return jsonify(error=f"Bad request: {e}"), 400


if __name__ == "__main__":
    app.run(debug=True, port=5050)
