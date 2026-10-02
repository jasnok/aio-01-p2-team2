FROM python:3.12-slim@sha256:eeb8088e67610b37583880c7627e3931f087cba55a35810819e34a398f624a47

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements-constraints.txt /tmp/requirements-constraints.txt
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -c /tmp/requirements-constraints.txt -r /tmp/requirements.txt
COPY backend /app/backend

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
