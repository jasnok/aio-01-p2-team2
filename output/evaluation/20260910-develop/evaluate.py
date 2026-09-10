"""Auditable local evaluation of an immutable develop snapshot.

External LLM/MCP responses are explicitly scripted fixtures, not real searches.
This file never connects to a server or writes to the shared database.
Run with the evaluation venv Python from any directory.
"""
from __future__ import annotations

import asyncio
import ast
import copy
import hashlib
import inspect
import json
import logging
import os
from pathlib import Path
import platform
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack
from datetime import datetime, timezone
from collections import Counter

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "source"
sys.path.insert(0, str(SOURCE))
os.chdir(SOURCE)
os.environ.update(BACKEND_MOCK_MODE="true", LLM_PROVIDER="mock", REDIS_ENABLED="false")
from backend.app.agents import intake_agent as intake, runtime
from backend.app.agents.models import AgentState
from backend.app.agents.registry import get_agent_profile
from backend.app.services import legal_question_service as service, agent_run_service as runs
from backend.app.services.mock_store import store
from backend.app.schemas.legal import Evidence
from backend.app.providers.models import ProviderResult
from backend.app.main import app
from fastapi.testclient import TestClient
from tests.lawpath_100_dataset import cases
from tests.run_lawpath_100 import isolated
from frontend.services.api_legal_service import ApiLegalService

logging.basicConfig(filename=BASE / "diagnostic-stderr.log", level=logging.WARNING,
                    encoding="utf-8", force=True)

RECORDS = []
TOOLS = ["search_laws", "search_consultations", "search_cases", "search_legal_documents"]
QUESTIONS = {"housing": "주택 임대차 계약이 끝났는데 보증금을 못 받았습니다. 관련 자료를 찾아주세요.",
             "labor": "퇴직 후 회사가 퇴직금을 지급하지 않았습니다. 관련 자료를 찾아주세요.",
             "consumer": "상품을 주문하고 결제했는데 배송되지 않았습니다. 관련 자료를 찾아주세요."}


def save(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def record(kind, name, expected, observed, passed=None, **kwargs):
    row = dict(id=f"D{len(RECORDS)+1:03}", kind=kind, name=name,
               expected=expected, observed=observed,
               verdict="OBSERVED" if passed is None else "PASS" if passed else "FAIL", **kwargs)
    RECORDS.append(row)
    save("diagnostic-results.json", RECORDS)
    print(row["id"], row["verdict"], name, flush=True)
    return row


def decision(status="sufficient", **extra):
    return dict(status=status, message="시험용으로 고정한 입력 판단입니다.",
                follow_up_questions=["어떤 일이 있었는지 알려주세요."] if status=="needs_clarification" else [],
                checks=dict(situation="met", timing="not_required", relationship="met", request_evidence="met"),
                **extra)


class ScriptedProvider:
    def __init__(self, sequence):
        self.sequence = sequence
        self.calls = []

    def generate_structured(self, system_prompt, message, response_schema):
        idx = len(self.calls)
        output = self.sequence[min(idx, len(self.sequence)-1)]
        entry = dict(call=idx+1, schema=response_schema.__name__, system_prompt=system_prompt,
                     input=message, output=copy.deepcopy(output) if not isinstance(output, Exception) else None)
        self.calls.append(entry)
        if isinstance(output, Exception):
            entry["error_type"] = type(output).__name__
            entry["error"] = str(output)
            raise output
        return ProviderResult("scripted-fixture", "no-model", copy.deepcopy(output), 0)


def fake_evidence(tool, category, number):
    typ = {"search_laws":"law", "search_cases":"case", "search_consultations":"consultation",
           "search_legal_documents":"law"}[tool]
    ident = f"fixture-{category}-{tool}-{number}"
    return dict(evidence_id=ident, document_id=ident, title=f"시험자료 {typ} {number}",
                content="이 문서는 프로그램 검증용 합성 근거입니다. 실제 법령이나 판례가 아닙니다.",
                source=dict(source_id=ident, title="합성 시험자료", source_type=typ,
                            url=f"https://example.invalid/{ident}"))


def pipeline(category, scenario):
    calls, events = [], []
    provider = ScriptedProvider([decision("needs_clarification" if scenario=="missing" else "sufficient")])
    async def event(value):
        events.append(copy.deepcopy(value))
    def search_for(name):
        async def search(query, category, top_k):
            entry = dict(tool=name, query=query, category=category, top_k=top_k)
            calls.append(entry)
            if scenario == "timeout":
                entry["error"] = "TimeoutError"
                raise TimeoutError("controlled MCP timeout")
            if scenario == "rate_limit":
                output = dict(success=False, error=dict(code="RATE_LIMIT", message="controlled rate limit"))
            elif scenario == "invalid_schema":
                output = dict(success=True, data={"unexpected":"not a list"})
            else:
                items = [] if scenario == "empty" else [fake_evidence(name, category, n) for n in range(1,4)]
                output = dict(success=True, data={"items":items} if name=="search_legal_documents" else items)
            entry["output"] = output
            return output
        return search
    with ExitStack() as stack:
        stack.enter_context(patch.object(intake, "get_settings", lambda: SimpleNamespace(llm_provider="openai", input_assessment_timeout_seconds=2)))
        stack.enter_context(patch.object(intake, "get_provider", lambda _: provider))
        for name in TOOLS:
            stack.enter_context(patch.object(runtime, name, search_for(name)))
        # Execute the unchanged run orchestration, including SSE terminal conversion.
        run, _ = runs.create_run(dict(id="evaluation-local",role="USER"), category,
                                 QUESTIONS[category], f"{category}-{scenario}", save_selected=False)
        asyncio.run(runs.execute_run(run["run_id"]))
    response = copy.deepcopy(runs.public_run(run))
    result = response.get("result") or {}
    view = ApiLegalService.adapt_analysis(result, QUESTIONS[category]) if result else None
    selected = [x["tool"] for x in calls]
    expected_tools = ["search_laws","search_consultations","search_cases"] if category=="consumer" else ["search_cases","search_legal_documents"]
    if scenario=="normal":
        ok = response["status"]=="completed" and selected==expected_tools and sum(len(result.get(k,[])) for k in ["related_laws","similar_cases","consultations"]) == (9 if category=="consumer" else 6)
    elif scenario=="missing":
        ok = response["status"]=="stopped" and not calls and bool(result.get("follow_up_questions"))
    elif scenario=="empty":
        ok = result.get("termination_reason")=="no_results" and not any(result.get(k) for k in ["related_laws","similar_cases","consultations"])
    else:
        ok = response["status"]=="failed" and len(calls)==1 and run["events"][-1]["event"]=="run.failed"
    return record("pipeline",f"{category}/{scenario}",
                  "normal: expected tool order and evidence counts; missing: no search and clarification; empty: no_results; faults: failed terminal without leaks",
                  dict(response=response, calls=calls, events=copy.deepcopy(run["events"]),
                       provider_calls=provider.calls, frontend_view=view), ok,
                  scope="real backend orchestration + scripted intake/MCP + template answer; no network",
                  category=category, scenario=scenario)


def retry_comparison():
    # The counterfactual differs in exactly one loop bound. Both arms validate output.
    source = inspect.getsource(intake.IntakeAgent)
    assert source.count("range(2)")==1
    before_source = source.replace("range(2)", "range(1)")
    (BASE / "intake-before-ablation.py.txt").write_text(before_source, encoding="utf-8")
    inputs = [
        ("valid", [decision()], True),
        ("bad_status_then_valid", [decision("unknown"),decision()], True),
        ("partial_checks_then_valid", [dict(status="sufficient",message="시험", checks={"situation":"met"}),decision()],True),
        ("invalid_twice", [decision("unknown"),decision("unknown")],False),
        ("provider_timeout", [TimeoutError("controlled provider timeout")],False),
    ]
    for category, question in QUESTIONS.items():
        for name, sequence, valid_expected in inputs:
            for arm in ["before_one_attempt", "after_develop_two_attempts"]:
                provider = ScriptedProvider(sequence)
                events = []
                async def event(value): events.append(value)
                with patch.object(intake,"get_provider",lambda _:provider), patch.object(intake,"get_settings",lambda:SimpleNamespace(llm_provider="openai",input_assessment_timeout_seconds=2)):
                    cls = intake.IntakeAgent
                    if arm.startswith("before"):
                        namespace = dict(vars(intake))
                        exec(compile(before_source, "<one-attempt-ablation>", "exec"), namespace)
                        cls = namespace["IntakeAgent"]
                    start = time.perf_counter()
                    try:
                        result = asyncio.run(cls().assess(category,question,event_callback=event))
                        observed = dict(completed=True,result=result.model_dump())
                    except Exception as error:
                        observed = dict(completed=False,error_type=type(error).__name__,error=str(error),
                                        cause_type=type(error.__cause__).__name__ if error.__cause__ else None)
                observed.update(provider_calls=provider.calls, events=events, retries=max(0,len(provider.calls)-1),
                                elapsed_seconds=round(time.perf_counter()-start,6))
                record("retry_ablation",f"{category}/{name}/{arm}",
                       "measure valid IntakeResult return; persistent invalid/timeout must safely fail",
                       observed, None, category=category, scenario=name, arm=arm,
                       scope="scripted provider; one-attempt counterfactual vs unchanged develop; no real model")


def answer_guards():
    evidence = Evidence.model_validate(fake_evidence("search_laws","consumer",1))
    scenarios = [
        ("valid_grounded",dict(question_summary="자료 확인",answer=evidence.content,used_evidence_ids=[evidence.evidence_id]),True),
        ("unknown_evidence_id",dict(question_summary="거짓",answer="이 문장에는 근거가 없습니다.",used_evidence_ids=["not-retrieved"]),False),
        ("valid_id_false_claim",dict(question_summary="거짓",answer="이 사건은 반드시 승소하며 보상액은 999999999원입니다.",used_evidence_ids=[evidence.evidence_id]),False),
        ("empty_ids_false_claim",dict(question_summary="거짓",answer="이 사건은 반드시 승소하며 보상액은 999999999원입니다.",used_evidence_ids=[]),False),
        ("provider_timeout",TimeoutError("controlled answer timeout"),False),
    ]
    for name, output, should_accept in scenarios:
        provider = ScriptedProvider([output])
        with patch.object(service,"get_provider",lambda _:provider), patch.object(service,"get_settings",lambda:SimpleNamespace(llm_provider="openai")):
            draft, used = asyncio.run(service.answer_with_llm(category="consumer",question=QUESTIONS["consumer"],evidence=[evidence]))
        record("answer_guard",name,"accept grounded answer; reject nonexistent citation, unsupported claim and timeout",
               dict(draft=draft.model_dump(),llm_used=used,provider_calls=provider.calls,evidence=evidence.model_dump()),
               used==should_accept,scope="injected answer; tests post-generation guard, not live model hallucination rate")


def boundary_checks():
    # API fields are schema validated before the route starts a run.
    with TestClient(app) as client:
        for payload in [dict(question=QUESTIONS["consumer"]),dict(category="consumer"),dict(category="consumer",question="a")]:
            before = len(store.agent_runs)
            r = client.post("/api/agent-runs",headers={"X-Guest-Id":"eval-boundary","Idempotency-Key":hashlib.sha256(json.dumps(payload).encode()).hexdigest()},json=payload)
            record("api_boundary","missing_or_short_field","422; no agent run created",dict(input=payload,http_status=r.status_code,response=r.json(),new_runs=len(store.agent_runs)-before),r.status_code==422 and len(store.agent_runs)==before)
    # A semantic clarification response without a question is currently schema-valid.
    output = decision("needs_clarification")
    output["follow_up_questions"] = []
    provider = ScriptedProvider([output])
    with patch.object(intake,"get_provider",lambda _:provider),patch.object(intake,"get_settings",lambda:SimpleNamespace(llm_provider="openai",input_assessment_timeout_seconds=2)):
        result = asyncio.run(intake.IntakeAgent().assess("consumer","문제가 생겼습니다. 도와주세요."))
    record("input_guard","clarification_without_question","needs_clarification must return at least one actionable follow-up",
           dict(result=result.model_dump(),provider_calls=provider.calls),bool(result.follow_up_questions))
    # Source counter increments only after successful await, so failure attempts are absent.
    calls=[]
    async def fail(*args,**kwargs):
        calls.append(dict(args=args,kwargs=kwargs))
        raise TimeoutError("controlled runtime timeout")
    state = AgentState(request_id="eval-counter",agent_id="consumer",question=QUESTIONS["consumer"])
    with patch.object(runtime,"search_laws",fail):
        try: asyncio.run(runtime.LegalAgentRuntime().run(get_agent_profile("consumer"),state))
        except TimeoutError: pass
    record("observability","failed_tool_attempt_counter","record attempted call even on failure",dict(actual_attempts=len(calls),state=state.model_dump()),state.tool_calls==len(calls))
    for group in ["검색 결과 없음","API 타임아웃","인증 실패"]:
        case = next(c for c in cases() if c["group"]==group)
        try: observed=isolated(case)
        except Exception as error: observed=dict(error_type=type(error).__name__,error=str(error))
        record("legacy_runner",case["id"],"existing isolated runner reaches agent and returns a verdict",observed,"verdict" in observed,input=case)


def inventory():
    items=[]
    for p in sorted(SOURCE.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or ".pytest_cache" in p.parts: continue
        data=p.read_bytes()
        row=dict(path=p.relative_to(SOURCE).as_posix(),size=len(data),sha256=hashlib.sha256(data).hexdigest())
        if p.suffix==".py":
            try:
                tree=ast.parse(data,filename=str(p))
                row.update(syntax="ok",functions=sum(isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) for n in ast.walk(tree)),classes=sum(isinstance(n,ast.ClassDef) for n in ast.walk(tree)))
            except Exception as e: row.update(syntax="error",error=str(e))
        items.append(row)
    save("source-inventory.json",items)
    save("environment.json",dict(started_at=datetime.now(timezone.utc).isoformat(),python=sys.version,platform=platform.platform(),
          commit="45e216ef9c291d4d62b0cccb9feb05b1135a55ac",snapshot_sha256=hashlib.sha256((BASE/"source.zip").read_bytes()).hexdigest(),
          source_files=len(items),python_files=sum("syntax" in x for x in items),api_key_present=bool(os.getenv("OPENAI_API_KEY")),
          mode="isolated scripted dependencies; no external LLM/MCP/DB"))
    save("planned-100-dataset.json",cases())


def main():
    inventory()
    for category in QUESTIONS:
        for scenario in ["normal","missing","empty","timeout"]:
            pipeline(category,scenario)
    pipeline("consumer","rate_limit")
    pipeline("consumer","invalid_schema")
    retry_comparison()
    answer_guards()
    boundary_checks()
    groups={kind:dict(Counter(r["verdict"] for r in RECORDS if r["kind"]==kind)) for kind in sorted({r["kind"] for r in RECORDS})}
    comparison={}
    for arm in ["before_one_attempt","after_develop_two_attempts"]:
        rows=[r for r in RECORDS if r["kind"]=="retry_ablation" and r["arm"]==arm]
        comparison[arm]=dict(trials=len(rows),valid_results=sum(r["observed"]["completed"] for r in rows),
                             retries=sum(r["observed"]["retries"] for r in rows),
                             safe_failures=sum(not r["observed"]["completed"] for r in rows))
    save("diagnostic-summary.json",dict(groups=groups,retry_comparison=comparison,total_records=len(RECORDS)))
    print(json.dumps(groups,ensure_ascii=False),flush=True)


if __name__=="__main__": main()
