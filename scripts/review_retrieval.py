"""Offline, blinded review of retrieved chunks; never creates human labels."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def review_cases(data):
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ValueError("검색 결과 records 목록이 필요합니다.")
    cases = []
    seen = set()
    for record in data["records"]:
        if not isinstance(record, dict):
            raise ValueError("검색 결과 레코드는 객체여야 합니다.")
        if not isinstance(record.get("kind"), str):
            raise ValueError("검색 레코드 kind 문자열이 필요합니다.")
        if record["kind"] != "natural" or record.get("error"):
            continue
        if not isinstance(record.get("id"), str) or not record["id"] or record["id"] in seen:
            raise ValueError("질문 ID가 없거나 중복되었습니다.")
        seen.add(record["id"])
        if not isinstance(record.get("query"), str) or not record["query"].strip():
            raise ValueError("질문 문자열이 필요합니다.")
        if not isinstance(record.get("variants"), dict) or not record["variants"]:
            raise ValueError("검색 비교 방식이 필요합니다.")
        documents = {}
        for name, variant in record["variants"].items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError("검색 방식 이름이 필요합니다.")
            if not isinstance(variant, dict):
                raise ValueError("검색 방식 결과는 객체여야 합니다.")
            arrays = [variant.get(field) for field in ("document_ids", "titles", "chunks")]
            if any(not isinstance(values, list) for values in arrays) or len({len(values) for values in arrays}) != 1:
                raise ValueError("문서 ID·제목·청크 목록 길이가 다릅니다.")
            ids, titles, chunks = arrays
            if any(type(value) is not int or value <= 0 for value in ids) or len(set(ids)) != len(ids):
                raise ValueError("문서 ID가 잘못되었거나 중복되었습니다.")
            if any(not isinstance(value, str) for value in titles + chunks):
                raise ValueError("제목과 청크는 문자열이어야 합니다.")
            for doc_id, title, chunk in zip(variant["document_ids"], variant["titles"], variant["chunks"]):
                item = documents.setdefault(str(doc_id), {"title": title, "chunks": []})
                if chunk not in item["chunks"]:
                    item["chunks"].append(chunk)
        cases.append({"id": record["id"], "query": record["query"], "documents": documents})
    return cases


def fingerprint(data):
    return hashlib.sha256(json.dumps(review_cases(data), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def score(data, labels):
    if not isinstance(labels, dict):
        raise ValueError("검토 점수는 객체여야 합니다.")
    if labels.get("dataset_fingerprint") != fingerprint(data):
        raise ValueError("검토한 데이터와 검색 결과가 다릅니다.")
    if not isinstance(labels.get("reviewer"), str) or not labels["reviewer"].strip():
        raise ValueError("검토자 이름이 필요합니다.")
    cases = {case["id"]: case for case in review_cases(data)}
    grades = labels.get("grades", {})
    if not isinstance(grades, dict) or set(grades) - set(cases):
        raise ValueError("검토 대상 밖의 질문이 있거나 점수 형식이 잘못되었습니다.")
    completed = {}
    for case_id, case in cases.items():
        values = grades.get(case_id, {})
        if not isinstance(values, dict) or set(values) - set(case["documents"]):
            raise ValueError("검토 대상 밖의 문서 점수가 있습니다.")
        if any(type(value) is not int or not 0 <= value <= 3 for value in values.values()):
            raise ValueError("점수는 0~3 정수여야 합니다.")
        if case["documents"] and set(values) == set(case["documents"]):
            completed[case_id] = {doc: values[doc] for doc in case["documents"]}
    scores = {}
    for record in data["records"]:
        if record.get("kind") != "natural" or record.get("error") or record.get("id") not in completed:
            continue
        values = completed[record["id"]]
        ideal = sorted(values.values(), reverse=True)[:3]
        ideal_dcg = sum((2 ** grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(ideal))
        for name, variant in record["variants"].items():
            # One conservative pooled-document grade: minimum relevance over
            # all viewed chunks. This metric compares document ordering and
            # does not measure differences between variants' chunk selection.
            ranked = [values[str(doc)] for doc in variant["document_ids"][:3]]
            dcg = sum((2 ** grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(ranked))
            scores.setdefault(name, []).append({"id": record["id"],
                "precision_at_3": sum(grade >= 2 for grade in ranked) / 3,
                "pooled_ndcg_at_3": dcg / ideal_dcg if ideal_dcg else 0})
    return {"scope": "blinded pooled retrieved-chunk relevance; not corpus recall or legal accuracy",
            "reviewer": labels["reviewer"], "dataset_fingerprint": fingerprint(data),
            "reviewed_queries": len(completed), "total_queries": len(cases),
            "pending_queries": len(cases) - len(completed),
            "empty_candidate_queries": sum(not case["documents"] for case in cases.values()),
            "summary": {name: {"query_count": len(rows),
                "precision_at_3": sum(row["precision_at_3"] for row in rows) / len(rows),
                "pooled_ndcg_at_3": sum(row["pooled_ndcg_at_3"] for row in rows) / len(rows)}
                for name, rows in scores.items()}, "records": scores}


HTML = '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>검색 근거 검토</title>
<style>body{font:16px/1.7 system-ui;max-width:1000px;margin:40px auto;padding:0 24px;background:#f5f7fb;color:#17243b}article{background:white;padding:24px;margin:20px 0;border:1px solid #dde3ec;border-radius:12px}pre{white-space:pre-wrap;font:14px/1.8 system-ui}button,select,input{padding:10px;font:inherit}header{position:sticky;top:0;background:#f5f7fb;padding:12px 0}h3{margin-bottom:8px}</style>
<h1>자연어 검색 근거 검토</h1><p>검색 방식과 순위는 숨겼습니다. 제목뿐 아니라 표시된 모든 청크를 읽고 보수적으로 평가하세요. 한 문서의 여러 청크가 다르면 가장 낮은 관련성을 선택하세요.</p>
<p>0 무관 · 1 주제만 비슷함 · 2 질문 일부를 뒷받침함 · 3 핵심 질문을 직접 뒷받침함. 원문 자체의 법적 정확성·최신성은 별도 검토 대상입니다.</p>
<header><input id="reviewer" placeholder="검토자 이름"><button id="save">검토 JSON 저장</button><input id="load" type="file" accept=".json"><span id="status"></span></header><main id="cases"></main>
<script>const source=__DATA__;const grades={};const root=document.getElementById('cases');
function text(tag,value,parent){const e=document.createElement(tag);e.textContent=value;parent.append(e);return e}
for(const c of source.cases){const a=document.createElement('article');root.append(a);text('h2',c.query,a);grades[c.id]={};
for(const [id,d] of Object.entries(c.documents).sort((a,b)=>Number(a[0])-Number(b[0]))){text('h3',d.title+' · 자료 '+id,a);for(const chunk of d.chunks)text('pre',chunk,a);
const s=document.createElement('select');s.dataset.case=c.id;s.dataset.doc=id;a.append(s);for(const [v,label] of [['','미검토'],['0','0 무관'],['1','1 주제 유사'],['2','2 부분 근거'],['3','3 직접 근거']]){const o=document.createElement('option');o.value=v;o.textContent=label;s.append(o)}s.onchange=()=>{if(s.value==='')delete grades[c.id][id];else grades[c.id][id]=Number(s.value);update()}}}
function update(){document.getElementById('status').textContent=' 검토 '+Object.values(grades).reduce((n,g)=>n+Object.keys(g).length,0)+'건'}
document.getElementById('save').onclick=()=>{const reviewer=document.getElementById('reviewer').value.trim();if(!reviewer){alert('검토자 이름을 입력하세요.');return}const data={reviewer,dataset_fingerprint:source.fingerprint,grades};const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='relevance-labels.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};
document.getElementById('load').onchange=async e=>{try{const d=JSON.parse(await e.target.files[0].text());if(d.dataset_fingerprint!==source.fingerprint)throw Error('데이터 불일치');document.getElementById('reviewer').value=d.reviewer||'';for(const s of document.querySelectorAll('select')){const v=d.grades?.[s.dataset.case]?.[s.dataset.doc];s.value=Number.isInteger(v)&&v>=0&&v<=3?String(v):'';s.onchange()}}catch(err){alert('불러오기 실패: '+err.message)}};update();</script></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="output/portfolio/retrieval-comparison.json")
    parser.add_argument("--html", default="output/optimization/relevance-review.html")
    parser.add_argument("--labels")
    parser.add_argument("--output", default="output/optimization/relevance-metrics.json")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    path = Path(args.html)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"fingerprint": fingerprint(data), "cases": review_cases(data)}, ensure_ascii=False).replace("<", "\\u003c")
    path.write_text(HTML.replace("__DATA__", payload), encoding="utf-8")
    if args.labels:
        metrics = score(data, json.loads(Path(args.labels).read_text(encoding="utf-8")))
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(metrics["summary"], ensure_ascii=False))
    else:
        print(f"{len(review_cases(data))}개 질문 검토표 생성. 사람의 관련성 평가는 대기 중입니다: {path}")


if __name__ == "__main__":
    main()
