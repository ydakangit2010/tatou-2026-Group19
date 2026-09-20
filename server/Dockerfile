# Server image: minimal Flask + Gunicorn
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git ca-certificates openssh-client gosu \
    && rm -rf /var/lib/apt/lists/*

# Dedicated unprivileged application account
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 \
       --no-create-home --shell /usr/sbin/nologin appuser

# Copy project description and install dependencies
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -e .

# Copy application
COPY src /app/src
COPY flag /app/flag
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh \
    && pip install --no-cache-dir -e .

EXPOSE 5000

CMD ["./entrypoint.sh"]
