import os
import uuid

import httpx
from dotenv import load_dotenv


load_dotenv()
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")


def get_backend_health() -> dict:
    response = httpx.get(f"{BACKEND_API_URL}/health", timeout=5)
    response.raise_for_status()
    return response.json()


def ask_legal_question(category: str, message: str) -> dict:
    response = httpx.post(
        f"{BACKEND_API_URL}/api/legal/questions",
        json={"session_id": f"demo-{uuid.uuid4()}", "category": category, "message": message},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()

