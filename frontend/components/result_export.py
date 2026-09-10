from datetime import datetime
import logging

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
    consultations = "\n\n".join(
        f"### [상담사례 {index}] {item['title']}\n\n{item['content']}"
        for index, item in enumerate(result.get("consultations", []), 1)
    ) or "- 없음"
    notice = "이 문서는 DEMO 데이터를 사용한 참고 자료이며 법률 자문이나 판결 예측이 아닙니다." if result.get("is_mock", True) else "이 문서는 검색된 자료를 정리한 참고 자료이며 법률 자문이나 판결 예측이 아닙니다."
    return f"""# LawPath 사례 분석 결과

생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}

> {notice}

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

## 소비자원 상담사례

{consultations}
"""


def render_result_download(result: dict) -> None:
    try:
        from frontend.components.pdf_export import build_analysis_pdf
        pdf = build_analysis_pdf(result)
    except ImportError:
        logging.getLogger(__name__).error("PDF dependency unavailable")
        st.warning("PDF 기능 준비가 필요합니다. 실행 환경의 PDF 라이브러리 설치를 확인해 주세요.")
        return
    except Exception as error:
        # Do not log user text or exception messages that may contain document content.
        logging.getLogger(__name__).error("PDF generation failed: %s", type(error).__name__)
        st.warning("PDF를 생성하지 못했습니다. 분석 결과는 화면에서 확인할 수 있습니다.")
        return
    st.download_button(
        "⬇️ 분석 결과 PDF 저장",
        data=pdf,
        file_name=f"lawpath-{result.get('agent_id', 'result')}-analysis.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
