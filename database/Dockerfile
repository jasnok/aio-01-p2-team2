FROM python:3.12-slim@sha256:eeb8088e67610b37583880c7627e3931f087cba55a35810819e34a398f624a47

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/database
COPY requirements-constraints.txt /tmp/requirements-constraints.txt
COPY database/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -c /tmp/requirements-constraints.txt -r /tmp/requirements.txt
COPY database /app/database

# One-off utility image only. Use `docker compose run --rm database-tools ...`.
CMD ["python", "--version"]
