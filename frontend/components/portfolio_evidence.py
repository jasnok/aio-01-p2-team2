import streamlit as st
from pydantic import ValidationError

from frontend.core.portfolio_evidence import load_evidence


def render_portfolio_evidence():
    with st.expander("엔지니어링 측정 결과", expanded=False):
        st.caption("저장된 로컬 측정 자료입니다. 이 화면은 API 요청을 보내지 않습니다.")
        try:
            report = load_evidence()
        except (OSError, ValueError, ValidationError):
            st.warning("측정 자료를 확인할 수 없습니다. 자료를 재생성해 주세요.")
            return
        st.warning("SDK 생성·키워드 DB 조회만 측정했습니다. 전체 상담 속도나 법률 정확도 평가가 아닙니다.")
        choice = st.selectbox("측정 범위", ["키워드 DB 조회", "SDK 클라이언트 획득"], key="portfolio-measurement")
        kind = "keyword" if choice == "키워드 DB 조회" else "embedding"
        labels = {"housing": "주거", "labor": "노동", "consumer": "소비자", None: "SDK 획득"}
        rows = [{"측정": labels[row.category], "변경 전(ms)": row.before_ms,
                 "변경 후(ms)": row.after_ms, "표본 수": row.samples, "준비 횟수": row.warmup,
                 "Python": row.python, "동등 결과 비교 쌍": row.equivalent_pairs}
                for row in report.rows if row.experiment == kind]
        st.dataframe(rows, hide_index=True)
        import pandas as pd
        st.bar_chart(pd.DataFrame(rows).set_index("측정")[["변경 전(ms)", "변경 후(ms)"]])
        st.caption("중앙값 비교이며 p95·추론 시간·검색 관련성 향상은 측정하지 않았습니다.")
        st.caption("측정 시점의 커밋·데이터 버전은 원본에 미기록입니다. 사람에 의한 법률 정확도 채점도 미완료입니다.")
        st.markdown("**환경 검증 기록**")
        st.dataframe([{"플랫폼": env.platform, "Python": env.python, "설치 패키지": env.packages,
                       "불일치": env.errors} for env in report.environments], hide_index=True)
        with st.expander("원본 JSON 내용과 SHA-256"):
            st.caption("키 정렬·공백 제거한 JSON 내용의 해시이며 파일 줄바꿈 방식에 영향을 받지 않습니다.")
            st.dataframe([source.model_dump() for source in report.sources], hide_index=True)
        st.download_button("측정 요약 JSON", report.model_dump_json(indent=2),
                           file_name="lawpath-portfolio-evidence.json", mime="application/json")
