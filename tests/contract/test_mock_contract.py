from backend.app.schemas.legal import LegalDocument
from legal_mcp.schemas.tools import SearchLegalDocumentsInput
from legal_mcp.tools.search import search_legal_documents


def test_mcp_items_match_backend_legal_document_contract() -> None:
    result = search_legal_documents(
        SearchLegalDocumentsInput(query="퇴직금을 받지 못했습니다", category="labor")
    )
    assert result.success is True
    for item in result.data["items"]:
        LegalDocument.model_validate(item)

