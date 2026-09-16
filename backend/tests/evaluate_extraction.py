"""知识抽取准确率验收脚本；通过后输出精确率、召回率、F1，不预设阈值。"""
import asyncio, json
from pathlib import Path
from app.services.extractor import KnowledgeExtractor

cases = json.loads((Path(__file__).parent / 'fixtures' / 'extraction_eval.json').read_text(encoding='utf-8'))
rows = []
for case in cases:
    result = asyncio.run(KnowledgeExtractor().extract(case['text']))
    actual = {p['name'].strip() for p in result['knowledge_points']}
    expected = set(case['expected_points'])
    tp = len(actual & expected)
    precision = tp / len(actual) if actual else 0
    recall = tp / len(expected) if expected else 1
    rows.append({'id':case['id'], 'precision':precision, 'recall':recall,
                 'f1':2*precision*recall/(precision+recall) if precision+recall else 0,
                 'actual_points':sorted(actual), 'expected_points':sorted(expected)})
report = {'case_count':len(rows), 'mean_precision':round(sum(x['precision'] for x in rows)/len(rows),3),
          'mean_recall':round(sum(x['recall'] for x in rows)/len(rows),3),
          'mean_f1':round(sum(x['f1'] for x in rows)/len(rows),3), 'cases':rows}
out = Path(__file__).parent/'artifacts'/'extraction_evaluation.json'; out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(report,ensure_ascii=False,indent=2))
