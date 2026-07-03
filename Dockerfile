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
