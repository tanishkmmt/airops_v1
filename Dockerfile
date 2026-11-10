FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services ./services
RUN addgroup --system --gid 10001 airops && adduser --system --uid 10001 --ingroup airops airops
USER 10001:10001
EXPOSE 8000

ARG SERVICE_MODULE
ENV SERVICE_MODULE=${SERVICE_MODULE}
CMD ["sh", "-c", "uvicorn ${SERVICE_MODULE}:app --host 0.0.0.0 --port 8000"]
