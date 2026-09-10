"""Run 75 real API/SSE questions + 25 isolated fault scenarios.
Run: python -m tests.run_lawpath_100
Outputs synthetic requests and server responses, never authorization headers.
"""
import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
import subprocess
from time import monotonic
from unittest.mock import patch
from uuid import uuid4

from tests.lawpath_100_dataset import cases


def isolated(case):
    from backend.app.agents.models import IntakeResult
    from backend.app.services import agent_run_service as service
    from backend.app.services.mock_store import store
    from backend.app.agents import runtime
    from backend.app.agents.intake_agent import IntakeAgent
    events = []
    calls = []
    if case['group'] == '인증 실패':
        from fastapi.testclient import TestClient
        from backend.app.main import app
        before = len(store.agent_runs)
        with TestClient(app) as client:
            response = client.post('/api/agent-runs', headers={'Authorization': 'Bearer invalid-eval-' + case['id'],
                'Idempotency-Key': str(uuid4())}, json={'category': case['category'], 'question': case['question']})
        return dict(verdict='PASS' if response.status_code in (401,403) and len(store.agent_runs)==before else 'FAIL',
                    http_status=response.status_code, response=response.json(), scope='local authorization route')

    async def assess(*args, **kwargs):
        return IntakeResult(is_ready_for_search=True,status='sufficient',message='격리시험 입력 판단 대체')
    async def search(*args, **kwargs):
        calls.append('search')
        if case['group'] == 'API 타임아웃':
            raise TimeoutError('injected timeout')
        return {'success': True, 'data': []}
    with ExitStack() as stack:
        stack.enter_context(patch.object(IntakeAgent, 'assess', assess))
        for name in ['search_cases','search_laws','search_consultations','search_legal_documents']:
            stack.enter_context(patch.object(runtime, name, search))
        run, _ = service.create_run({'id':'isolated-eval'},case['category'],case['question'],str(uuid4()))
        asyncio.run(service.execute_run(run['run_id']))
        result = run.get('result') or {}
        events = run['events']
        if case['group'] == 'API 타임아웃':
            ok = run['status']=='failed' and len(calls) > 0 and any(e['event']=='run.failed' for e in events)
        else:
            ok = bool(calls) and result.get('termination_reason')=='no_results' and not any(
                result.get(k) for k in ['related_laws','similar_cases','consultations']) and bool(result.get('answer'))
        return dict(verdict='PASS' if ok else 'FAIL', response=service.public_run(run), events=events,
                    injected_search_calls=len(calls), scope='local runtime; intake stubbed; no real DB/LLM')


def live(case, prefix):
    from frontend.clients import backend_client as api
    from frontend.clients.agent_stream import receive_run
    from frontend.services.api_legal_service import ApiLegalService
    from frontend.core.config import get_frontend_settings
    guest = prefix + '-' + case['id']
    events = []
    run_id = None
    try:
        created = api.create_agent_run(None,guest,case['category'],case['question'],guest)
        run_id = created['run_id']
        def event(number, kind, data):
            events.append(dict(id=number,event=kind,data=data))
        raw = receive_run(None,guest,run_id,on_event=event)
        view = ApiLegalService.adapt_analysis(raw,case['question'])
        counts = {key:len(raw.get(key,[])) for key in ['related_laws','similar_cases','consultations']}
        tools = [e['data'].get('tool') for e in events if e['event']=='step.started' and e['data'].get('tool')]
        if case['group'] == '정상 요청':
            ok = raw['status']=='completed' and not raw['is_mock'] and sum(counts.values())>0
            verdict = 'PASS' if ok else 'FAIL'
        elif case['group'] == '정보 부족':
            ok = raw.get('termination_reason')=='needs_clarification' and bool(raw.get('follow_up_questions'))
            verdict = 'FAIL' if not ok or tools else 'REVIEW' if not events else 'PASS'
        else:
            verdict = 'REVIEW'
        return dict(verdict=verdict, run_id=run_id, response=raw, events=events, tools=tools,
                    counts=counts, frontend_state=view['result_state'], scope='live frontend client → backend SSE; no browser',
                    target=get_frontend_settings().normalized_backend_url,
                    nine_results=(list(counts.values()) == [3,3,3]) if case['id']=='T035' else None)
    except Exception as error:
        return dict(verdict='ERROR',run_id=run_id,events=events,error_type=type(error).__name__,
                    error_code=getattr(error,'code',None),scope='live frontend client')


def main():
    rows = cases()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    out = Path('output/evaluation') / stamp
    out.mkdir(parents=True,exist_ok=True)
    (out/'dataset.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    lines = ['# LawPath 시험 데이터 100개','', '| ID | 유형 | 분야 | 질문 | 실행 | 기대 결과 |', '|---|---|---|---|---|---|']
    lines += [f"| {r['id']} | {r['group']} | {r['category']} | {r['question']} | {r['mode']} | {r['expected']} |" for r in rows]
    (out/'질문목록.md').write_text('\n'.join(lines),encoding='utf-8')
    records=[]
    def execute(case):
        start=monotonic()
        try:
            result=isolated(case) if case['mode']=='isolated' else live(case,'eval-'+stamp)
        except Exception as e:
            result=dict(verdict='ERROR',error_type=type(e).__name__)
        return {**case,**result,'elapsed_seconds':round(monotonic()-start,3)}
    def record(result):
        records.append(result)
        (out/(result['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        print(result['id'],result['verdict'],result['elapsed_seconds'],flush=True)
    print('OUTPUT',out,flush=True)
    for case in rows:
        if case['mode']=='isolated': record(execute(case))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(execute,r) for r in rows if r['mode']=='live']
        for future in as_completed(futures): record(future.result())
    records.sort(key=lambda r:r['id'])
    (out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    groups={g:dict(Counter(r['verdict'] for r in records if r['group']==g)) for g in dict.fromkeys(r['group'] for r in rows)}
    report=['# LawPath 100건 시험 결과','',f"로컬 코드: {subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}",
            '배포 서버 커밋은 미확인. 문항은 합성 데이터이며 개인 정보가 아닙니다.',
            'PASS는 자동 구조·흐름 기준 통과입니다. 법률 정답률/근거 관련성/할루시네이션 검증 완료를 뜻하지 않습니다.',
            '실서버 75건과 격리 오류시험 25건의 결과를 혼합하여 Agent 성공률로 사용하지 마세요.',
            '자기 성찰 적용 전후 비교, 실제 모델 재시도 횟수, 도구 선택 정확도 및 답변 일관성은 미측정입니다.',
            '', '| 유형 | 자동 통과 | 실패 | 실행 오류 | 수동 검토 |','|---|---:|---:|---:|---:|']
    for g,v in groups.items(): report.append(f"| {g} | {v.get('PASS',0)} | {v.get('FAIL',0)} | {v.get('ERROR',0)} | {v.get('REVIEW',0)} |")
    report += ['', '## 문항별 결과','', '| ID | 판정 | 시간(초) |','|---|---|---:|']
    report += [f"| {r['id']} | {r['verdict']} | {r['elapsed_seconds']} |" for r in records]
    (out/'시험결과.md').write_text('\n'.join(report),encoding='utf-8')
    print(json.dumps(groups,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
