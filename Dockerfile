FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY README.md ./

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.rss_note_writer", "--log-level", "INFO", "--config-file", "/app/src/rss_note_writer/config/rss_configs.json"]
