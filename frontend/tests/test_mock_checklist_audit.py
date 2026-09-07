from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "app.py"


def _open_labor_workspace() -> AppTest:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button(key="category-labor").click().run(timeout=20)
    return app


def _submit_analysis(app: AppTest, question: str) -> AppTest:
    app.text_area(key="question_message").set_value(question)
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click()
    return app.run(timeout=20)


def test_checklist_normal_analysis_and_evidence_render() -> None:
    app = _submit_analysis(_open_labor_workspace(), "퇴직했는데 퇴직금을 받지 못했습니다.")

    assert not app.exception
    assert app.session_state["last_result"]["status"] == "completed"
    assert app.session_state["analysis_in_progress"] is False
    assert app.session_state["analysis_error"] is None
    assert len(app.session_state["last_result"]["related_laws"]) >= 1
    assert len(app.session_state["last_result"]["similar_cases"]) >= 1
    visible = "\n".join(item.value for item in (*app.markdown, *app.caption, *app.info))
    assert "Agent 진행 상태" in visible
    assert "근거 L1" in visible
    assert "근거 C1" in visible
    assert "승소 가능성" in visible
    assert app.get("download_button")


def test_checklist_error_then_retry_success() -> None:
    app = _open_labor_workspace()
    app.session_state["mock_scenario"] = "mcp_error"
    app = _submit_analysis(app, "퇴직금 관련 판례를 확인해 주세요.")

    assert app.session_state["last_result"] is None
    assert app.session_state["analysis_error"]["code"] == "MCP_UNAVAILABLE"
    assert app.session_state["analysis_error"]["stage"] == "판례 검색"
    assert app.session_state["analysis_error"]["next_action"]

    app.session_state["mock_scenario"] = "success"
    app = _submit_analysis(app, "퇴직금 관련 판례를 확인해 주세요.")
    assert app.session_state["analysis_error"] is None
    assert app.session_state["last_result"]["status"] == "completed"


def test_checklist_no_evidence_does_not_render_invented_sources() -> None:
    app = _open_labor_workspace()
    app.session_state["mock_scenario"] = "no_evidence"
    app = _submit_analysis(app, "퇴직금 지급 근거를 확인해 주세요.")

    result = app.session_state["last_result"]
    assert result["result_state"] == "no_evidence"
    assert result["related_laws"] == []
    assert result["similar_cases"] == []
    assert any("공식 근거가 부족" in item.value for item in app.warning)


def test_checklist_follow_up_and_new_analysis() -> None:
    app = _submit_analysis(_open_labor_workspace(), "퇴직했는데 퇴직금을 받지 못했습니다.")
    first_history_size = len(app.session_state["session_history"])

    app.text_input(key="follow_up_input").set_value("1년 3개월 근무했다면 어떻게 확인하나요?")
    next(button for button in app.button if button.label == "후속 질문 분석").click()
    app = app.run(timeout=20)

    assert len(app.session_state["conversation_messages"]) == 2
    assert len(app.session_state["session_history"]) == first_history_size + 1
    assert app.session_state["last_result"]["parent_request_id"]

    app.button(key="new-analysis").click()
    app = app.run(timeout=20)
    assert app.session_state["last_result"] is None
    assert app.session_state["conversation_messages"] == []
