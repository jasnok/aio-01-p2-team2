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
        st.warning("SDK 생성·키워드 DB 조회·로컬 공개 HTTP GET 단계의 측정입니다. 전체 상담 속도나 법률 정확도 평가가 아닙니다.")
        scopes = {"키워드 DB 조회": "keyword", "SDK 클라이언트 획득": "embedding", "HTTP 연결 재사용": "http"}
        choice = st.selectbox("측정 범위", list(scopes), key="portfolio-measurement")
        kind = scopes[choice]
        if kind == 'http':
            st.caption('인증·모델 요청 없는 localhost 공개 카탈로그 GET입니다. 기존 경로는 클라이언트 생성·종료를 포함합니다.')
        labels = {"housing": "주거", "labor": "노동", "consumer": "소비자", None: "SDK 획득"}
        rows = [{"측정": labels[row.category], "변경 전(ms)": row.before_ms,
                 "변경 후(ms)": row.after_ms, "표본 수": row.samples, "준비 횟수": row.warmup,
                 "Python": row.python, "동등 결과 비교 쌍": row.equivalent_pairs}
                for row in report.rows if row.experiment == kind]
        st.dataframe(rows, hide_index=True)
        import pandas as pd
        st.bar_chart(pd.DataFrame(rows).set_index("측정")[["변경 전(ms)", "변경 후(ms)"]])
        st.caption("중앙값 비교이며 p95·추론 시간·검색 관련성 향상은 측정하지 않았습니다.")
        st.caption("사람에 의한 법률 정확도 채점은 미완료입니다.")
        provenance = report.provenance.get(kind)
        if provenance is None:
            st.caption("측정 시점의 커밋·데이터 버전은 원본에 미기록입니다.")
        else:
            with st.expander("측정 시점의 코드·환경·데이터 출처"):
                st.write(f"측정 시작(UTC): {provenance.started_at.isoformat()}")
                st.write(f"Git HEAD: {provenance.git_head or '미기록'}")
                st.write(f"미커밋 변경 포함: {provenance.working_tree_dirty}")
                st.caption("Git HEAD와 실행 코드가 같다고 가정하지 않습니다. 실행 파일 해시를 함께 확인하세요.")
                if provenance.database_before:
                    st.write(f"문서 {provenance.database_before.documents}개 · 청크 {provenance.database_before.chunks}개")
                    st.write(f"선언된 revision: {provenance.database_before.revision_declared}")
                    st.caption("시작·종료 데이터 규모 비교이며 변경 불가능한 DB 스냅샷 버전은 아닙니다.")
                st.json(provenance.model_dump(mode="json"))
        st.markdown("**환경 검증 기록**")
        st.dataframe([{"플랫폼": env.platform, "Python": env.python, "설치 패키지": env.packages,
                       "불일치": env.errors} for env in report.environments], hide_index=True)
        with st.expander("원본 JSON 내용과 SHA-256"):
            st.caption("키 정렬·공백 제거한 JSON 내용의 해시이며 파일 줄바꿈 방식에 영향을 받지 않습니다.")
            st.dataframe([source.model_dump() for source in report.sources], hide_index=True)
        st.download_button("측정 요약 JSON", report.model_dump_json(indent=2),
                           file_name="lawpath-portfolio-evidence.json", mime="application/json")
