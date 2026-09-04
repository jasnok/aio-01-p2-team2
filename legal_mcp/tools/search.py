from legal_mcp.schemas.tools import SearchLegalDocumentsInput, ToolResponse


CATEGORY_LABELS = {
    "housing": "임대차·주거",
    "labor": "근로·임금",
    "consumer": "중고거래·소비자 분쟁",
}


def _mock_document(document_type: str, category: str, index: int) -> dict:
    label = CATEGORY_LABELS[category]
    return {
        "evidence_id": f"evidence-{document_type.lower()}-{category}-{index}",
        "document_id": f"mock-{document_type.lower()}-{category}-{index}",
        "title": f"{label} {document_type} Mock 자료 {index}",
        "summary": "서버 간 연결과 응답 계약을 확인하기 위한 Mock 자료입니다.",
        "content": "실제 법률 원문이 아닙니다. RAG 구현 시 검증된 데이터로 교체합니다.",
        "source": {
            "source_id": f"mock-source-{document_type.lower()}-{index}",
            "title": "MOCK_DATA",
            "source_type": document_type.lower(),
            "url": "https://example.invalid/mock-data",
        },
        "score": 1.0 - (index * 0.1),
        "metadata": {"is_mock": True},
    }


def search_legal_documents(arguments: SearchLegalDocumentsInput) -> ToolResponse:
    items = []
    for index, document_type in enumerate(arguments.document_types[: arguments.top_k], start=1):
        items.append(_mock_document(document_type, arguments.category, index))
    return ToolResponse(
        success=True,
        data={"items": items},
        meta={
            "query": arguments.query,
            "result_count": len(items),
            "retrieval_method": "mock",
            "is_mock": True,
        },
    )
