import json
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "산출물 2 에이전트 시험 결과 보고서.docx"
NAVY = "1F4E78"
PALE = "EEF3F8"
GRID = "D9D9D9"


def set_cell_shading(cell, color):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def set_cell_border(cell):
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        tag = qn(f"w:{edge}")
        element = borders.find(tag)
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), GRID)


def set_repeat_table_header(row):
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def keep_row_together(row):
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def remove_paragraph_border(paragraph):
    p_pr = paragraph._p.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is not None:
        p_pr.remove(borders)


def remove_style_border(style):
    p_pr = style.element.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is not None:
        p_pr.remove(borders)


def set_cell_text(cell, value, bold=False, white=False, center=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.25
    r = p.add_run(str(value))
    r.bold = bold
    r.font.name = "Malgun Gothic"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    r.font.size = Pt(9.5)
    if white:
        r.font.color.rgb = RGBColor(255, 255, 255)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_cell_border(cell)


def add_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    table.style = "Table Grid"
    set_repeat_table_header(table.rows[0])
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_shading(cell, NAVY)
        set_cell_text(cell, header, bold=True, white=True, center=True)
        if widths:
            cell.width = Cm(widths[index])
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        keep_row_together(table.rows[-1])
        for index, value in enumerate(row):
            if row_index % 2:
                set_cell_shading(cells[index], PALE)
            set_cell_text(cells[index], value, center=(len(str(value)) < 18))
            if widths:
                cells[index].width = Cm(widths[index])
    doc.add_paragraph().paragraph_format.space_after = Pt(3)
    return table


def add_heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(13)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Malgun Gothic"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    r.font.size = Pt(17)
    return p


def add_text(doc, text, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1.45
    r = p.add_run(text)
    r.italic = italic
    r.font.name = "Malgun Gothic"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    r.font.size = Pt(10.5)
    return p


def add_bullets(doc, values):
    for value in values:
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.35
        r = p.add_run(value)
        r.font.name = "Malgun Gothic"
        r._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
        r.font.size = Pt(10.5)


def load_summary(name):
    path = ROOT / "output" / name
    return json.loads(path.read_text(encoding="utf-8"))["summary"]


def main():
    before = load_summary("synthetic_agent_comparison_before.json")
    after = load_summary("synthetic_agent_comparison.json")
    before_completion = before["task_completed"] / before["case_count"]
    after_completion = after["task_completed"] / after["case_count"]
    before_selection = before["tool_selection_correct"] / before["tool_selection_total"]
    after_selection = after["tool_selection_correct"] / after["tool_selection_total"]
    before_consistency = before["response_consistent"] / before["case_count"]
    after_consistency = after["response_consistent"] / after["case_count"]
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Cm(1.8)
    sec.bottom_margin = Cm(1.6)
    sec.left_margin = Cm(1.8)
    sec.right_margin = Cm(1.8)

    styles = doc.styles
    remove_style_border(styles["Title"])
    styles["Normal"].font.name = "Malgun Gothic"
    styles["Normal"]._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    styles["Normal"].font.size = Pt(10.5)

    title = doc.add_paragraph(style="Title")
    remove_paragraph_border(title)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(12)
    run = title.add_run("LawPath 에이전트 시험 결과 보고서")
    run.font.name = "Malgun Gothic"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    run.font.size = Pt(25)
    run.font.color.rgb = RGBColor(0, 0, 0)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(18)
    r = subtitle.add_run("자기 성찰 및 검증 흐름의 시험 근거와 측정 계획")
    r.font.name = "Malgun Gothic"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    r.font.size = Pt(13)
    r.font.color.rgb = RGBColor(80, 80, 80)

    add_text(doc, "본 보고서는 LawPath의 입력 판단, 도구 호출, 근거 검증, 안전한 종료 흐름을 시험한 결과를 정리한다. 비교 전 기준은 31edb7f, 비교 후 기준은 현재 BO 브랜치의 8fa7627로 고정했다. 전체 pytest 결과와 함께, 외부 서비스에 연결하지 않는 동일한 100건 로컬 모의 시험을 두 기준에 적용해 전후 지표를 산정했다.")

    add_heading(doc, "1 시험 목적")
    add_text(doc, "동일한 법률 질의 흐름에서 입력 부족 감지, 도구 선택, 도구 결과 검증, 근거 기반 응답 및 실패 처리의 동작을 확인한다. 특히 근거 부족 시 보완 검색, 검색 전 보완 질문, 검색되지 않은 근거 인용 차단이 안전하게 작동하는지 검증한다.")

    add_heading(doc, "2 시험 기준과 실행 환경")
    add_table(doc, ["구분", "기준", "설명"], [
        ["비교 전", "31edb7f", "근거 부족 시 MCP 보완 검색을 도입한 d01d96b 직전 상태"],
        ["비교 후", "8fa7627", "현재 BO 브랜치 HEAD. 입력 판단, 재시도, 근거 검증 및 폴백이 포함된 상태"],
        ["실행 명령", "pytest -q --disable-warnings", "GitHub Actions의 pytest 실행과 같은 전체 테스트 기준"],
        ["실행 환경", "Windows PowerShell, Python 3.12 가상환경", "프로젝트 루트와 별도 Git worktree에서 각각 실행"],
    ], [3.0, 3.1, 10.0])

    add_heading(doc, "3 시험 데이터와 확인 항목")
    add_table(doc, ["유형", "현재 자동 시험 근거", "확인 항목"], [
        ["정상 법률 질의", "test_legal_question_service, test_legal_mcp_runtime", "카테고리별 검색과 Evidence 기반 응답 생성"],
        ["입력 정보 부족", "test_intake_agent, test_legal_question_service", "검색 전 needs_clarification 및 후속 질문 반환"],
        ["도구 선택과 호출 한도", "test_legal_mcp_runtime, test_legal_mcp_client", "프로필별 도구 순서, trace, 최대 3회 호출"],
        ["MCP 실패와 빈 결과", "test_legal_search_api, test_legal_mcp_runtime", "실패 전파, no_results, 근거 없는 답변 방지"],
        ["응답 근거 불일치", "test_llm_answer_service, test_answer_agent", "검색되지 않은 evidence id 차단 및 템플릿 폴백"],
        ["SSE 및 중복 요청", "test_agent_stream, test_mock_api", "실행 이벤트, 재연결, idempotency 계약"],
    ], [3.3, 5.6, 7.2])

    add_heading(doc, "4 오류 감지 기준")
    add_bullets(doc, [
        "할루시네이션: AnswerDraft의 used_evidence_ids가 실제 검색된 Evidence ID 집합의 부분집합이 아니면 감지한다.",
        "도구 선택 오류: AgentProfile의 allowed_tools에 없는 도구이거나 카테고리별 고정 검색 순서를 벗어나면 정책 검증에서 차단한다.",
        "파라미터 또는 입력 정보 부족: IntakeResult가 needs_clarification이면 MCP 호출 전에 중단하고 최대 3개의 보완 질문을 반환한다.",
        "응답 불일치: 최종 응답이 검색된 Evidence와 연결되지 않거나 인용 ID 검증에 실패하면 LLM 결과를 사용하지 않는다.",
        "반복 초과: Runtime의 도구 호출 수가 최대 3회를 넘으려 하면 실행 오류로 종료한다.",
    ])

    add_heading(doc, "5 오류별 대응과 자기 성찰 흐름")
    add_table(doc, ["오류", "감지와 수정 전략", "재시도 또는 종료 조건"], [
        ["입력 판단 계약 오류", "구조화 출력 재요청", "시간 제한 내 최대 1회 재시도 후 IntakeAssessmentError"],
        ["입력 정보 부족", "도구 호출을 생략하고 보완 질문", "needs_clarification과 stopped로 종료"],
        ["MCP 도구 실패 또는 형식 오류", "오류를 RuntimeError로 전파", "run.failed와 일반화된 오류 안내"],
        ["검색 결과 0건", "근거 없는 내용 생성 금지", "no_results로 종료"],
        ["근거 3건 미만", "가능한 Evidence는 유지하고 주의사항 추가", "insufficient_evidence로 종료"],
        ["검색 외 근거 인용", "LLM 초안을 폐기하고 AnswerAgent 사용", "재시도 없이 안전한 폴백"],
    ], [3.4, 7.2, 5.5])

    add_heading(doc, "6 실제 pytest와 100건 모의 시험 결과")
    add_table(doc, ["기준", "실행 결과", "해석"], [
        ["비교 후 8fa7627", "243 passed, 4 skipped, 1 warning, 19.62s", "전체 pytest가 exit code 0으로 정상 종료"],
        ["비교 전 31edb7f", "105개 수집, 진행 표시 100% 후 종료 지연", "테스트 프로세스를 중단했으므로 성공률 수치로 사용하지 않음"],
    ], [3.1, 5.2, 7.8])
    add_text(doc, "태스크 완료율, 도구 선택 정확도, 응답 일관성, 평균 재시행 횟수는 pytest 통과율과 다른 측정값이다. 아래 수치는 동일한 가짜 MCP 응답을 주입한 로컬 Runtime 시험의 결과이며, 실제 법률 DB, 실제 LLM, 네트워크 지연 또는 법률 근거의 품질을 측정한 값이 아니다.", italic=True)
    add_table(doc, ["지표", "적용 전", "적용 후", "산식과 측정 상태"], [
        ["태스크 완료율", f"{before_completion:.0%} ({before['task_completed']}/100)", f"{after_completion:.0%} ({after['task_completed']}/100)", "기대 종료 상태와 Evidence 수를 충족한 건수 ÷ 100"],
        ["도구 선택 정확도", f"{before_selection:.0%} ({before['tool_selection_correct']}/{before['tool_selection_total']})", f"{after_selection:.0%} ({after['tool_selection_correct']}/{after['tool_selection_total']})", "현 설계의 분야별 다중 검색 순서와 실제 selector 비교. 호출 한도 초과 5건 제외"],
        ["응답 일관성", f"{before_consistency:.0%} ({before['response_consistent']}/100)", f"{after_consistency:.0%} ({after['response_consistent']}/100)", "종료 사유, Evidence 수, 안전한 오류 처리가 케이스 기대값과 일치한 비율"],
        ["평균 동일 도구 재시도", f"{before['average_same_tool_retries']:.1f}회", f"{after['average_same_tool_retries']:.1f}회", "Runtime에는 실패한 같은 도구의 자동 재시도가 없으므로 0.0회. 다른 검색 도구 호출은 재시도로 계산하지 않음"],
    ], [3.2, 2.4, 2.4, 8.1])

    add_heading(doc, "7 프롬프트와 파라미터 조정 이력")
    add_table(doc, ["변경 커밋", "발견 문제", "변경 내용", "검증 근거"], [
        ["d01d96b", "근거가 부족한 검색 결과", "MCP 보완 검색과 도구 선택 순서 보강", "Runtime의 추가 검색 및 Evidence 수 테스트"],
        ["9628926", "모호한 질문과 LLM 출력 형식", "LLM 기반 입력 충분성 판단, 구조화 출력 재시도, 인용 ID 검증", "입력 판단과 LLM 답변 서비스 테스트"],
        ["33436fc", "입력 체크의 세분화 필요", "입력 판단 체크와 선택 저장 대화 흐름 추가", "입력 판단 및 API 계약 테스트"],
    ], [2.5, 4.0, 6.4, 3.2])

    add_heading(doc, "8 재실행과 검증 계획")
    add_text(doc, "이번 보고서의 전후 지표는 동일한 100건 가짜 MCP 응답을 두 기준 커밋에 적용해 산정했다. 프로젝트에는 tests/run_lawpath_100.py와 별도의 100건 평가 데이터셋도 있으나, 이 도구는 현재 구현에서 추가되었고 실제 서버 연결을 포함한다. 따라서 본 모의 결과와 실제 서비스 품질 결과를 혼용하지 않는다.")
    add_bullets(doc, [
        "31edb7f와 8fa7627에 같은 시험 러너, 같은 100건, 같은 가짜 MCP 응답을 적용했다.",
        "각 실행의 request id, tool_selected와 tool_completed trace, termination_reason, used_evidence_ids를 원본 로그로 보관한다.",
        "정상 요청, 정보 부족, 빈 결과, 타임아웃, 인증 실패, 상충 지시를 동일한 비율로 포함한다.",
        "자동 판정 후 법률 근거의 관련성, 인용 정확성, 제한사항 안내는 사람 검토로 별도 기록한다.",
        "프로세스 종료 지연이 재현되면 해당 현상을 별도 결함으로 등록하고, 완료 지표와 분리해 보고한다.",
    ])

    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fr = footer.add_run("LawPath Agent Test Report")
    fr.font.name = "Malgun Gothic"
    fr.font.size = Pt(8.5)
    fr.font.color.rgb = RGBColor(120, 120, 120)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
