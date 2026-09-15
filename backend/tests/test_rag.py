"""LightRAG / Self-RAG 核心逻辑单元测试。"""

import json
import asyncio
import unittest

from app.services.rag import RAGService


class TestRAGService(unittest.TestCase):
    def test_retrieval_gate_skips_only_simple_greetings(self):
        self.assertFalse(RAGService._needs_retrieval("你好"))
        self.assertFalse(RAGService._needs_retrieval("谢谢！"))
        self.assertTrue(RAGService._needs_retrieval("什么是装饰器？"))

    def test_parse_reflection_accepts_markdown_json(self):
        payload = {
            "support": 0.7,
            "relevance": 0.9,
            "completeness": 0.8,
            "retry": False,
            "feedback": "证据充分",
        }
        parsed = RAGService._parse_reflection(
            "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
        )
        self.assertEqual(parsed["support"], 0.7)
        self.assertFalse(parsed["retry"])

    def test_merge_references_deduplicates_and_keeps_best_score(self):
        local = [{
            "neo4j_id": "kp_1", "name": "装饰器", "score": 0.8,
            "source_type": "local",
        }]
        graph = [{
            "neo4j_id": "kp_1", "name": "装饰器", "score": 0.4,
            "source_type": "graph",
        }, {
            "neo4j_id": "kp_2", "name": "闭包", "score": 0.5,
            "source_type": "graph",
        }]
        merged = RAGService._merge_references(local, graph)
        self.assertEqual([item["neo4j_id"] for item in merged], ["kp_1", "kp_2"])
        self.assertEqual(merged[0]["source_type"], "local")

    def test_ask_retries_after_failed_self_check(self):
        service = RAGService()
        service._ready = True
        service.self_rag_enabled = True

        base_refs = [{
            "neo4j_id": "kp_1", "name": "装饰器", "description": "装饰器用于扩展函数行为",
            "score": 0.8, "source_type": "local",
        }]
        expanded_refs = base_refs + [{
            "neo4j_id": "kp_2", "name": "闭包", "description": "闭包可保存外层作用域状态",
            "score": 0.5, "source_type": "graph", "relation": "RELATED_TO",
            "connected_from": "装饰器",
        }]
        service._retrieve_lightrag = (
            lambda question, course_id=None, expanded=False:
            expanded_refs if expanded else base_refs
        )

        responses = iter([
            "初次回答",
            '{"support":0.4,"relevance":0.9,"completeness":0.7,'
            '"retry":true,"feedback":"补充闭包证据"}',
            "基于补充证据的回答",
        ])
        service._call_llm = lambda *args, **kwargs: next(responses)

        result = asyncio.run(service.ask("装饰器与闭包有什么关系？", course_id=1))
        self.assertEqual(result["answer"], "基于补充证据的回答")
        self.assertTrue(result["rag_meta"]["retried"])
        self.assertEqual(result["rag_meta"]["retrieved"], 2)


if __name__ == "__main__":
    unittest.main()
