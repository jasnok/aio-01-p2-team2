from fastapi import FastAPI

from legal_mcp.schemas.tools import LawArticleInput, SearchInput, SearchLegalDocumentsInput, ToolResponse, ToolResult
from legal_mcp.tools.get_law_article import get_law_article
from legal_mcp.tools.search import search_legal_documents
from legal_mcp.tools.search_cases import search_cases
from legal_mcp.tools.search_laws import search_laws


app = FastAPI(title="Legal MCP Mock Server", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "mode": "mock", "database": "not_connected"}


@app.post("/tools/search_legal_documents", response_model=ToolResponse)
def run_search(arguments: SearchLegalDocumentsInput) -> ToolResponse:
    return search_legal_documents(arguments)


@app.post("/tools/search_laws", response_model=ToolResult)
def run_search_laws(arguments: SearchInput) -> ToolResult:
    return search_laws(arguments)


@app.post("/tools/search_cases", response_model=ToolResult)
def run_search_cases(arguments: SearchInput) -> ToolResult:
    return search_cases(arguments)


@app.post("/tools/get_law_article", response_model=ToolResult)
def run_get_law_article(arguments: LawArticleInput) -> ToolResult:
    return get_law_article(arguments)
