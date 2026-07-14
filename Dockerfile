FROM python:3.12-slim

WORKDIR /app

# Install system deps for psycopg2 (used by Alembic)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

RUN useradd -m botuser
USER botuser

CMD ["python", "-m", "bot.main"]
