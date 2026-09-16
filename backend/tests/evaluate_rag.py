"""离线 RAG 验收脚本：记录响应时间、引用命中率和可见幻觉线索。"""
import json, os, statistics, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
cases = json.loads((ROOT / 'fixtures' / 'rag_eval.json').read_text(encoding='utf-8'))
base, token = os.getenv('RAG_EVAL_BASE_URL', 'http://127.0.0.1:8000/api'), os.getenv('RAG_EVAL_TOKEN')
if not token: raise SystemExit('请设置 RAG_EVAL_TOKEN 后执行 python tests/evaluate_rag.py')
rows = []
for case in cases:
    request = urllib.request.Request(base + '/qa/ask', data=json.dumps({'question':case['question'],'course_id':case['course_id']}).encode(), method='POST', headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=90) as response: answer = json.loads(response.read())
    sources, text = {s.get('name','') for s in answer.get('sources',[])}, answer.get('answer','')
    rows.append({'id':case['id'],'latency_ms':round((time.perf_counter()-started)*1000,1),'citation_recall':sum(n in sources for n in case['must_cite'])/len(case['must_cite']),'hallucination_flag':any(c in text for c in case.get('forbidden_claims',[])),'source_count':len(sources)})
report = {'case_count':len(rows),'median_latency_ms':statistics.median(r['latency_ms'] for r in rows),'citation_recall':round(statistics.mean(r['citation_recall'] for r in rows),3),'hallucination_flag_rate':round(statistics.mean(r['hallucination_flag'] for r in rows),3),'cases':rows}
out = ROOT/'artifacts'/'rag_evaluation.json'; out.parent.mkdir(exist_ok=True); out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
