# Beauty Extension Haus — booking webhook receiver (Square + Mangomint).
# Stdlib-only Python, no pip deps. Reachable only over the compose network, via
# nginx (`web`) proxying /api/hook/*. No host ports.
FROM python:3.12-slim

WORKDIR /app
COPY server.py .

ENV PYTHONUNBUFFERED=1 \
    HOOKS_FILE=/data/hooks.jsonl \
    PORT=8080

EXPOSE 8080
CMD ["python3", "server.py"]
