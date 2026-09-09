import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("category,expected", [
    ("housing", "주택 임대차 계약이 끝났는데 임대인이 보증금을 돌려주지 않습니다. 어떤 법 조문을 확인해야 하나요?"),
    ("labor", "퇴직했는데 회사가 퇴직금을 지급하지 않습니다. 퇴직금 지급 기한과 관련 법 조문을 알려주세요."),
    ("consumer", "신용카드 일시불 결제 후 할부로 전환했는데 물건이 배송되지 않았습니다. 카드사에 할부항변권을 행사할 수 있나요?"),
])
def test_button_loads_exact_question(category, expected):
    app = AppTest.from_string(
        "from frontend.core.session import initialize_session\n"
        "from frontend.components.question_form import render_question_form\n"
        "initialize_session()\n"
        f"render_question_form({category!r})\n"
    ).run()
    app.button[0].click().run()
    assert not app.exception
    assert app.text_area(key="question_message").value == expected
