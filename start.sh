#!/bin/sh
set -e

JOBS_DIR="${SCROOGE_JOBS_DIR:-/var/scrooge/jobs}"
mkdir -p "$JOBS_DIR/queue"

python worker.py &
exec gunicorn --workers 1 --threads 4 --timeout 120 --bind "0.0.0.0:${PORT:-8000}" app:app
