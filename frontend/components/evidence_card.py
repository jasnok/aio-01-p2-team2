"""법령·판례·상담사례 공통 카드. 출처 데이터는 보존하고 링크 UI만 제외."""
import streamlit as st
from math import isfinite
import re
from html import escape


def readable_text(text: str) -> str:
    """Add whitespace only: preserve legal wording, dates and amounts."""
    text = re.sub(r'(?<!\n)(?=(?:법령명|조문 제목|조문|사건명|사건번호|법원|선고일|구분|내용|제목|품목|질문|답변)\s*:)', '\n\n', text)
    text = re.sub(r'(?<!\n)(?=[①-⑳]|\[\d+\])', '\n\n', text)
    text = re.sub(r'(?<!\S)(?=(?:\(\d+\)|\d+(?:의\d+)?\.(?!\d)\s))', '\n\n', text)
    text = re.sub(r'(?<=[.!?])\s+(?=[가-힣])', '\n\n', text)
    return text.strip()


def evidence_html(text: str) -> str:
    paragraphs = [part.strip() for part in re.split(r'\n\s*\n', readable_text(text)) if part.strip()]
    blocks = ''.join(
        '<p style="margin:0 0 1.15em;line-height:1.95;white-space:pre-wrap;overflow-wrap:anywhere;text-align:left;">'
        + escape(part) + '</p>' for part in paragraphs
    )
    return '<div class="lawpath-evidence-body" style="max-width:78ch;padding:0.35rem 0.25rem;">' + blocks + '</div>'


def score_label(score) -> str:
    if type(score) not in (int, float) or not isfinite(score) or not 0 <= score <= 1:
        return "관련도 미제공"
    return f"검색 점수 {score:.3f}"


def preview(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 150 else text[:149] + "…"


def render_evidence_card(item: dict, index: int, kind: str) -> None:
    label = {"law": "법령", "case": "판례", "consultation": "상담사례"}[kind]
    content = item.get("content") or item.get("detail") or item.get("summary") or item.get("result") or "내용이 없습니다."
    summary = item.get("summary") or content
    with st.container(border=True):
        st.markdown(f"#### [{label} {index}] {item['title']}")
        st.caption(score_label(item.get("score")))
        st.markdown(evidence_html(preview(summary)), unsafe_allow_html=True)
        with st.expander("상세보기"):
            if kind == "law":
                st.caption(item.get("article") or item.get("article_number") or "조문 정보 없음")
            elif kind == "case":
                metadata = [item.get("court"), item.get("case_number"), item.get("date") or item.get("decided_at")]
                st.caption(" · ".join(str(value) for value in metadata if value and "정보 없음" not in str(value)) or "판례 상세 정보 미제공")
            st.caption("법령 본문" if kind == "law" else "판례 본문" if kind == "case" else "상담 내용")
            st.markdown(evidence_html(content), unsafe_allow_html=True)
            st.caption("검색 점수는 검색 순위 산정용이며 법률 적용 가능성이나 답변 정확도를 뜻하지 않습니다. 자료 종류 간 점수는 직접 비교하지 마세요.")
            if item.get("is_mock", False):
                st.caption("화면 확인용 예시 자료입니다.")
