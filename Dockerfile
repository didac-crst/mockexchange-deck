# ---------- build stage ----------
FROM python:3.12-slim AS build
WORKDIR /opt/app

# install Poetry
RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* ./
# install prod deps into the global site‑packages (not venv)
RUN poetry config virtualenvs.create false \
 && poetry install --no-dev --no-root --no-interaction --no-ansi

COPY app app

# ---------- runtime stage ----------
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH" \
    PORT=8501
WORKDIR /opt/app

# copy installed libs & source
COPY --from=build /usr/local/lib/python*/site-packages /usr/local/lib/python*/site-packages
COPY app app
COPY .env.example .env  # overridden in CI/CD or docker‑compose

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.headless=true"]