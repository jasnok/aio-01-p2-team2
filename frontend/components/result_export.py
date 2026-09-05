from datetime import datetime

import streamlit as st


def build_analysis_markdown(result: dict) -> str:
    issues = "\n".join(f"- {item}" for item in result.get("key_issues", [])) or "- 없음"
    laws = "\n".join(
        f"- **{item['title']}** — {item.get('article', '조문 정보 없음')}: {item.get('summary', '')}"
        for item in result.get("related_laws", [])
    ) or "- 없음"
    cases = "\n".join(
        f"- **{item['title']}** ({item.get('case_number', '-')}, {item.get('date', '-')}) — {item.get('result', '')}"
        for item in result.get("similar_cases", [])
    ) or "- 없음"
    return f"""# LawPath 사례 분석 결과

생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}

> 이 문서는 DEMO 데이터를 사용한 참고 자료이며 법률 자문이나 판결 예측이 아닙니다.

## 입력한 상황

{result.get('question', '')}

## 상황 요약

{result.get('question_summary', '')}

## 핵심 쟁점

{issues}

## 분석 안내

{result.get('answer', '')}

## 관련 법령

{laws}

## 유사 판례

{cases}
"""


def render_result_download(result: dict) -> None:
    st.download_button(
        "⬇️ 분석 결과 Markdown 저장",
        data=build_analysis_markdown(result),
        file_name=f"lawpath-{result.get('agent_id', 'result')}-analysis.md",
        mime="text/markdown",
        use_container_width=True,
    )
