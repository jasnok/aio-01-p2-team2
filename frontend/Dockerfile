FROM python:3.12-slim@sha256:eeb8088e67610b37583880c7627e3931f087cba55a35810819e34a398f624a47

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY requirements-constraints.txt /tmp/requirements-constraints.txt
COPY frontend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -c /tmp/requirements-constraints.txt -r /tmp/requirements.txt
COPY frontend /app/frontend

EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "frontend/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
