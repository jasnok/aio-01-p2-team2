"""Deterministic legal query terms; no extra model call or invented facts."""

import re


LEGAL_TERMS = (
    "보증금", "임대차", "계약갱신", "내용증명", "퇴직금", "임금", "해고",
    "근로계약", "환불", "반품", "배송", "하자", "중고거래", "사기",
    "전자상거래", "청약철회", "손해배상", "계약해지", "수리", "위약금",
)


def extract_query_terms(query: str) -> list[str]:
    """Preserve exact identifiers and bounded legal terms found in the question."""
    normalized = re.sub(r"\s+", "", query)
    identifiers = re.findall(r"\d{4}[가-힣]{1,4}\d+|제\s*\d+\s*조(?:의\s*\d+)?", query)
    terms = [re.sub(r"\s+", "", item) for item in identifiers]
    terms.extend(term for term in LEGAL_TERMS if term in normalized)
    # Short explicit searches (law names, article numbers) retain exact matching.
    if len(query.strip()) <= 30:
        terms.insert(0, query.strip())
    return list(dict.fromkeys(terms))[:8] or [query.strip()]
