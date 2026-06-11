FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-kor \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

ENV PORT=8000
EXPOSE 8000
# Single worker: the job store is in-process memory. Use threads for concurrency.
CMD exec gunicorn --workers 1 --threads 8 --timeout 300 --bind 0.0.0.0:$PORT app:app
