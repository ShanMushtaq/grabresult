# GrabResult — container image (no paid services required)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GRABRESULT_DB_PATH=/data/grabresult.db \
    GRABRESULT_UPLOAD_DIR=/data/uploads \
    GRABRESULT_EXPORT_DIR=/data/exports

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN mkdir -p /data/uploads /data/exports

EXPOSE 7860
# Hugging Face Spaces (Docker SDK) requires the app on port 7860; Render.com
# sets $PORT itself — the shell form below honors both.
CMD gunicorn run:app --bind 0.0.0.0:${PORT:-7860} --workers 2 --threads 4 --timeout 120
