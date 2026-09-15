FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY frontend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY frontend /app/frontend

EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "frontend/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
