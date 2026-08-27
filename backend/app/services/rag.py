"""
RAG 智能问答服务
---------------
基于 DeepSeek + Neo4j + jieba 的 RAG 问答流水线：

  用户问题 → jieba 分词 → Neo4j 关键词检索 → 匹配相关知识点
           → requests 直连 DeepSeek → 生成回答 → 返回 {answer, references}

说明：
  - 使用 requests 直连 DeepSeek（与 extractor 一致，避免 httpx SSL 连接问题）
  - 检索主力：jieba 中文分词 + Neo4j 关键词匹配（不依赖 Embedding API）

使用方式：
    from app.services.rag import RAGService
    rag = RAGService()
    result = await rag.ask(question="傅里叶变换是什么？", course_id=1)
"""

import asyncio
from typing import List, Dict, Optional

import requests

from app.core.config import get_settings
from app.core.database import run_cypher

settings = get_settings()

# ============================================================
# RAG 提示词模板
# ============================================================

RAG_SYSTEM_PROMPT = """你是一个专业的课程 AI 助教，名为「知谱智航」。你的职责是基于课程知识库中的内容，
准确回答学生提出的问题。

请严格遵循以下规则：
1. 只根据【参考知识点】中提供的内容作答，不要使用你的先验知识
2. 如果参考内容不足以回答问题，请如实告知学生，并建议他们查阅教材或询问老师
3. 回答时请引用知识点的名称（用【知识点名称】标注）
4. 回答要结构清晰、通俗易懂，适合学生理解
5. 如果问题与课程内容无关，请礼貌地将话题引导回课程学习"""

RAG_USER_PROMPT = """【参考知识点】
{context}

【对话历史】
{history}

【学生问题】
{question}

请基于以上参考内容回答学生的问题："""


# ============================================================
# RAG 问答服务
# ============================================================

class RAGService:
    """
    基于 RAG 的智能问答服务

    流水线：
    1. Retrieval  — jieba 分词 + Neo4j 关键词检索
    2. Generation — requests 直连 DeepSeek 生成回答
    """

    def __init__(self):
        self._ready = bool(settings.DEEPSEEK_API_KEY and
                          settings.DEEPSEEK_API_KEY != "your-deepseek-api-key")
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
        self.model = settings.DEEPSEEK_MODEL

    # ---- LLM 调用 ----

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7,
                  max_tokens: int = 2000) -> str:
        """同步调用 DeepSeek chat completions（requests 直连）。"""
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
            proxies={"http": None, "https": None},  # 禁用系统代理
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    # ---- 公共接口 ----

    async def ask(
        self,
        question: str,
        course_id: Optional[int] = None,
        history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        执行 RAG 问答。

        Args:
            question:  学生提出的问题
            course_id: 课程数据库 ID（可选，为 None 则全局检索）
            history:   多轮对话历史，形如 [{"role": "user", "content": "..."},
                         {"role": "assistant", "content": "..."}, ...]

        Returns:
            {
                "answer": "回答文本",
                "references": [...],
                "suggested_questions": [...]
            }
        """
        # Step 1: 检索相关知识点
        references = self._retrieve(question, course_id)

        # Step 2: 构建上下文
        context = self._build_context(references)

        # Step 3: 生成回答
        if not context.strip():
            return {
                "answer": "抱歉，该课程的知识库中暂无相关内容可以回答你的问题。"
                          "建议你查阅教材或联系老师获取帮助。",
                "references": [],
                "suggested_questions": [],
            }

        if not self._ready:
            return {
                "answer": "RAG 服务未配置。请在 .env 中设置有效的 DEEPSEEK_API_KEY。\n\n"
                          f"已检索到 {len(references)} 个相关知识点，但无法调用大模型生成回答。",
                "references": [
                    {"neo4j_id": r["neo4j_id"], "name": r["name"], "score": r["score"]}
                    for r in references
                ],
                "suggested_questions": [],
            }

        user_prompt = (RAG_USER_PROMPT
                       .replace("{context}", context)
                       .replace("{history}", self._build_history(history))
                       .replace("{question}", question))

        messages = [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        answer = await asyncio.get_event_loop().run_in_executor(
            None, self._call_llm, messages, 0.7, 2000)

        return {
            "answer": answer,
            "references": [
                {"neo4j_id": r["neo4j_id"], "name": r["name"], "score": r["score"]}
                for r in references
            ],
            "suggested_questions": [],
        }

    @staticmethod
    def _build_history(history: Optional[List[Dict]]) -> str:
        """将多轮对话历史拼接为提示词文本。"""
        if not history:
            return "（无）"
        lines = []
        for msg in history[-6:]:  # 最多保留最近 6 条
            role = "学生" if msg.get("role") == "user" else "助教"
            content = (msg.get("content") or "").strip()
            if content:
                lines.append(f"{role}：{content[:300]}")
        return "\n".join(lines) if lines else "（无）"

    async def recommend_questions(self, course_id: Optional[int] = None) -> List[str]:
        """
        为课程生成推荐问题列表。
        """
        # 默认问题（无 Neo4j 或无知识点时使用）
        defaults = [
            "这门课程主要包含哪些知识点？",
            "各知识点之间有什么关联？",
            "我应该按照什么顺序学习这门课程？",
        ]

        try:
            if course_id:
                nodes = run_cypher(
                    """MATCH (kp:KnowledgePoint {course_id: $course_id})
                    RETURN kp.name AS name, kp.description AS description
                    ORDER BY kp.order_index LIMIT 5""",
                    {"course_id": course_id},
                )
            else:
                nodes = run_cypher(
                    """MATCH (kp:KnowledgePoint)
                    RETURN kp.name AS name, kp.description AS description
                    ORDER BY kp.order_index LIMIT 5""",
                )
        except Exception:
            return defaults

        if not nodes:
            return [
                "这门课程主要包含哪些知识点？",
                "各知识点之间有什么关联？",
                "我应该按照什么顺序学习这门课程？",
            ]

        questions = []
        for node in nodes:
            q = await self._generate_question(
                node.get("name", ""),
                node.get("description", ""),
            )
            if q:
                questions.append(q)

        if not questions:
            kp_names = [n.get("name", "") for n in nodes[:3]]
            questions = [f"什么是{name}？" for name in kp_names if name]

        return questions

    # ---- 内部：检索 ----

    def _retrieve(
        self, question: str, course_id: Optional[int] = None, top_k: int = 5
    ) -> List[Dict]:
        """检索相关知识点。"""
        return self._keyword_search(question, course_id, top_k)

    def _keyword_search(
        self, question: str, course_id: Optional[int], top_k: int
    ) -> List[Dict]:
        """jieba 中文分词 + 关键词匹配检索。"""
        import jieba

        try:
            if course_id:
                nodes = run_cypher(
                    """MATCH (kp:KnowledgePoint {course_id: $course_id})
                    RETURN kp.neo4j_id AS neo4j_id, kp.name AS name, kp.description AS description""",
                    {"course_id": course_id},
                )
            else:
                nodes = run_cypher(
                    """MATCH (kp:KnowledgePoint)
                    RETURN kp.neo4j_id AS neo4j_id, kp.name AS name, kp.description AS description""",
                )
        except Exception:
            return []

        if not nodes:
            return []

        # 对问题分词
        keywords = set(jieba.cut(question))

        # 计算每个节点与问题的匹配分数
        scored = []
        for node in nodes:
            node_text = f"{node.get('name', '')} {node.get('description', '')}"
            node_words = set(jieba.cut(node_text))
            overlap = keywords & node_words
            if overlap:
                scored.append({
                    "neo4j_id": node["neo4j_id"],
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "score": round(len(overlap) / max(len(keywords), 1), 3),
                })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    # ---- 内部：上下文构建 ----

    def _build_context(self, references: List[Dict]) -> str:
        """将检索到的知识点拼接为 LLM 上下文"""
        if not references:
            return ""

        parts = []
        for i, ref in enumerate(references, 1):
            name = ref.get("name", "未知")
            desc = ref.get("description", "暂无描述")
            parts.append(f"知识点{i}：{name}\n内容：{desc}\n")

        return "\n".join(parts)

    # ---- 内部：推荐问题生成 ----

    async def _generate_question(self, name: str, description: str) -> str:
        """为一个知识点生成引导性问题"""
        if not self._ready:
            return f"什么是{name}？" if name else ""
        messages = [{
            "role": "system",
            "content": (
                f"为知识点「{name}」生成一个简短的、能引导学生思考的问题。"
                f"知识点内容：{description}"
                f"\n只输出问题本身，不要加任何前缀或引号。"
            ),
        }]
        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._call_llm, messages, 0.5, 300)
        except Exception:
            return f"什么是{name}？" if name else ""


# ============================================================
# 全局单例
# ============================================================

_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取 RAG 服务单例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
