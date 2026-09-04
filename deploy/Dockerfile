FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONIOENCODING=utf-8 PIP_NO_CACHE_DIR=1

COPY requirements.txt requirements-services.txt ./
RUN pip install -r requirements.txt -r requirements-services.txt

# Ядро ревью + промпты + сервисы + бенч (профиль eval регенерирует синтетику сам)
COPY tz_review ./tz_review
COPY prompts ./prompts
COPY services ./services
COPY eval ./eval
COPY synth ./synth
COPY casedata ./casedata
# Фронтенд аналитика (Streamlit) — сервис front
COPY app.py ./app.py
COPY .streamlit ./.streamlit

HEALTHCHECK --interval=15s --timeout=5s --retries=5 CMD ["python", "-c", "import sys, urllib.request; port = sys.argv[1] if len(sys.argv) > 1 else '8080'; urllib.request.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=3)"]
