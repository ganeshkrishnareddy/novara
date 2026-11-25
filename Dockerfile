# NOVARA application image.
# Local SQLite is the default; the postgres extra is installed so the same
# image can be pointed at PostgreSQL with NOVARA_DATABASE_URL. The migrate extra
# is required because startup applies Alembic before serving requests, so a
# fresh container gets a version-stamped schema instead of an unstamped create_all.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NOVARA_DB_PATH=/data/novara.sqlite3

WORKDIR /srv/novara

COPY apps/api/pyproject.toml ./
COPY apps/api/novara_core ./novara_core
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/migrations ./migrations
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir '.[postgres,migrate]'

COPY apps/web ./web

RUN useradd --create-home --uid 10001 novara \
    && mkdir -p /data \
    && chown -R novara:novara /srv/novara /data
USER novara

VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

# Apply schema migrations to the mounted database, then hand off to uvicorn.
# The app's create_all() stays as a harmless no-op once the tables exist.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn novara_core.main:app --host 0.0.0.0 --port 8000"]
