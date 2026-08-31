from fastapi import FastAPI

from schemas.tools import SearchLegalDocumentsInput, ToolResponse
from tools.search import search_legal_documents


app = FastAPI(title="Legal MCP Mock Server", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "mock", "database": "not_connected"}


@app.post("/tools/search_legal_documents", response_model=ToolResponse)
def run_search(arguments: SearchLegalDocumentsInput) -> ToolResponse:
    return search_legal_documents(arguments)

