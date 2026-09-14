FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 orbitalai \
    && useradd \
       --uid 10001 \
       --gid orbitalai \
       --create-home \
       orbitalai

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY ingestion ./ingestion
COPY orbital_engine ./orbital_engine

RUN python -m pip install --upgrade pip \
    && python -m pip install ".[platform]" \
    && python -c "import fastapi, sqlalchemy, psycopg, prometheus_client, uvicorn; print('OrbitalAI platform dependencies OK')"

USER orbitalai

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
