"""법령·판례·상담사례 공통 카드. 출처 데이터는 보존하고 링크 UI만 제외."""
import streamlit as st


def preview(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 150 else text[:149] + "…"


def render_evidence_card(item: dict, index: int, kind: str) -> None:
    label = {"law": "법령", "case": "판례", "consultation": "상담사례"}[kind]
    content = item.get("content") or item.get("detail") or item.get("summary") or item.get("result") or "내용이 없습니다."
    summary = item.get("summary") or content
    with st.container(border=True):
        st.markdown(f"#### [{label} {index}] {item['title']}")
        st.write(preview(summary))
        with st.expander("상세보기"):
            if kind == "law":
                st.caption(item.get("article") or item.get("article_number") or "조문 정보 없음")
            elif kind == "case":
                st.caption(" · ".join(str(item.get(key) or "정보 없음") for key in ("court", "case_number")))
                st.caption(str(item.get("date") or item.get("decided_at") or "선고일 정보 없음"))
            st.write(content)
            if item.get("is_mock", False):
                st.caption("화면 확인용 예시 자료입니다.")
