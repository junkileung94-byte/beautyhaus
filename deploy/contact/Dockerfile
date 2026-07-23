# Beauty Extension Haus — public contact-form receiver.
# Stdlib-only Python, no pip deps. Reachable only over the compose network,
# via nginx (`web`) proxying the single path /api/message. No host ports.
FROM python:3.12-slim

WORKDIR /app
COPY server.py .

ENV PYTHONUNBUFFERED=1 \
    MESSAGES_FILE=/data/messages.jsonl \
    PORT=8080

EXPOSE 8080
CMD ["python3", "server.py"]
