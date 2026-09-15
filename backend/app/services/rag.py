"""
RAG 智能问答服务
---------------
基于 DeepSeek + Neo4j + jieba 的 LightRAG + Self-RAG 问答流水线：

  用户问题 → 检索门控 → 局部知识点/图谱邻域/课程模块融合检索
           → DeepSeek 生成 → 证据自检 → 必要时扩展检索并重答

说明：
  - 使用 requests 直连 DeepSeek（与 extractor 一致，避免 httpx SSL 连接问题）
  - LightRAG：局部实体、图谱关系和全局模块三级证据融合
  - Self-RAG：回答支持度、相关性和完整性自检
  - 不依赖额外 Embedding API，沿用项目已有 DeepSeek 与 Neo4j

使用方式：
    from app.services.rag import RAGService
    rag = RAGService()
    result = await rag.ask(question="傅里叶变换是什么？", course_id=1)
"""

import asyncio
import json
import re
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

SELF_RAG_REFLECTION_PROMPT = """你是回答质量审查器。请检查回答是否被参考资料充分支持。

【参考资料】
{context}

【问题】
{question}

【待审查回答】
{answer}

只输出 JSON，不要输出解释：
{{"support": 0到1, "relevance": 0到1, "completeness": 0到1,
  "retry": true或false, "feedback": "一句简短改进建议"}}

判断标准：
1. support：回答中的事实是否能从参考资料找到依据
2. relevance：是否直接回答问题
3. completeness：是否覆盖问题的关键部分
4. 任一分数低于 0.68，或存在无依据内容时，retry 必须为 true"""

SELF_RAG_RETRY_PROMPT = """上一次回答未通过证据自检，请根据更完整的参考资料重新回答。
审查意见：{feedback}

要求：
1. 删除无法从参考资料验证的内容
2. 明确引用【知识点名称】
3. 直接回答问题，不要描述审查过程"""


# ============================================================
# RAG 问答服务
# ============================================================

class RAGService:
    """
    基于 RAG 的智能问答服务

    流水线：
    1. LightRAG  — 局部实体检索 + 图谱邻域扩展 + 全局模块检索
    2. Generation — DeepSeek 基于融合证据生成回答
    3. Self-RAG   — 证据支持度自检，必要时扩大检索并重生成
    """

    def __init__(self):
        self._ready = bool(settings.DEEPSEEK_API_KEY and
                          settings.DEEPSEEK_API_KEY != "your-deepseek-api-key")
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
        self.model = settings.DEEPSEEK_MODEL
        self.self_rag_enabled = settings.SELF_RAG_ENABLED

    # ---- LLM 调用 ----

    def _call_llm(self, messages: List[Dict], temperature: float = 0.7,
                  max_tokens: int = 2000) -> str:
        """同步调用 DeepSeek chat completions（requests 直连）。"""
        try:
            # 不强制关闭系统代理。校园网、代理软件或受管 Windows 环境下，
            # 强制直连 api.deepseek.com 可能触发 WinError 10013。
            request_options = {}
            if settings.DEEPSEEK_PROXY:
                request_options["proxies"] = {
                    "http": settings.DEEPSEEK_PROXY,
                    "https": settings.DEEPSEEK_PROXY,
                }
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
                **request_options,
            )
        except requests.ConnectionError as exc:
            raise RuntimeError(
                "无法连接 DeepSeek 服务，请检查网络、代理设置以及 Windows 防火墙是否允许 python.exe 联网"
            ) from exc
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
        # Step 1: Self-RAG 判断是否需要课程知识检索。
        retrieval_needed = self._needs_retrieval(question)
        references = (
            self._retrieve_lightrag(question, course_id)
            if retrieval_needed else []
        )

        # Step 2: 构建上下文
        context = self._build_context(references)

        # Step 3: 生成回答
        if retrieval_needed and not context.strip():
            return {
                "answer": "抱歉，该课程的知识库中暂无相关内容可以回答你的问题。"
                          "建议你查阅教材或联系老师获取帮助。",
                "references": [],
                "suggested_questions": [],
                "rag_meta": {
                    "mode": "light+self-rag",
                    "retrieval_needed": True,
                    "retrieved": 0,
                    "self_check": "skipped",
                    "retried": False,
                },
            }

        if not retrieval_needed:
            context = "当前输入属于寒暄或简单交互，无需检索课程知识库。"

        if not self._ready:
            return {
                "answer": "RAG 服务未配置。请在 .env 中设置有效的 DEEPSEEK_API_KEY。\n\n"
                          f"已检索到 {len(references)} 个相关知识点，但无法调用大模型生成回答。",
                "references": [
                    {"neo4j_id": r["neo4j_id"], "name": r["name"], "score": r["score"]}
                    for r in references
                ],
                "suggested_questions": [],
                "rag_meta": {
                    "mode": "light+self-rag",
                    "retrieval_needed": retrieval_needed,
                    "retrieved": len(references),
                    "self_check": "skipped",
                    "retried": False,
                },
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

        # Step 4: Self-RAG 证据自检；低分时扩大检索范围并重答一次。
        reflection = {
            "support": 1.0,
            "relevance": 1.0,
            "completeness": 1.0,
            "retry": False,
            "feedback": "",
        }
        retried = False
        if self.self_rag_enabled and retrieval_needed:
            reflection = await self._reflect(question, answer, context)
            if (settings.SELF_RAG_MAX_RETRIES > 0
                    and self._should_retry(reflection)):
                expanded = self._retrieve_lightrag(question, course_id, expanded=True)
                if expanded:
                    references = expanded
                    context = self._build_context(references)
                    retry_instruction = SELF_RAG_RETRY_PROMPT.format(
                        feedback=reflection.get("feedback", "补充证据并提高回答准确性"),
                    )
                    retry_prompt = (RAG_USER_PROMPT
                                    .replace("{context}", context)
                                    .replace("{history}", self._build_history(history))
                                    .replace("{question}", question))
                    retry_messages = [
                        {"role": "system", "content": RAG_SYSTEM_PROMPT},
                        {"role": "user", "content": f"{retry_instruction}\n\n{retry_prompt}"},
                    ]
                    answer = await asyncio.get_event_loop().run_in_executor(
                        None, self._call_llm, retry_messages, 0.35, 2200)
                    retried = True

        return {
            "answer": answer,
            "references": [
                {"neo4j_id": r["neo4j_id"], "name": r["name"], "score": r["score"]}
                for r in references
            ],
            "suggested_questions": [],
            "rag_meta": {
                "mode": "light+self-rag",
                "retrieval_needed": retrieval_needed,
                "retrieved": len(references),
                "local_count": sum(1 for r in references if r.get("source_type") == "local"),
                "graph_count": sum(1 for r in references if r.get("source_type") == "graph"),
                "global_count": sum(1 for r in references if r.get("source_type") == "global"),
                "self_check": reflection,
                "retried": retried,
            },
        }

    @staticmethod
    def _needs_retrieval(question: str) -> bool:
        """Self-RAG 的检索门控：寒暄无需访问知识库，其余问题默认检索。"""
        normalized = re.sub(r"[\s，。！？,.!?]", "", question).lower()
        greetings = {"你好", "您好", "嗨", "hello", "hi", "谢谢", "再见"}
        return normalized not in greetings

    async def _reflect(self, question: str, answer: str, context: str) -> Dict:
        """让模型从证据支持度、相关性和完整性三个维度审查回答。"""
        prompt = (SELF_RAG_REFLECTION_PROMPT
                  .replace("{context}", context[:7000])
                  .replace("{question}", question)
                  .replace("{answer}", answer[:4000]))
        messages = [{"role": "user", "content": prompt}]
        try:
            raw = await asyncio.get_event_loop().run_in_executor(
                None, self._call_llm, messages, 0.0, 500)
            return self._parse_reflection(raw)
        except Exception as exc:
            # 自检失败不影响主回答，保留诊断信息供排查。
            return {
                "support": 1.0,
                "relevance": 1.0,
                "completeness": 1.0,
                "retry": False,
                "feedback": f"自检不可用：{type(exc).__name__}",
            }

    @staticmethod
    def _parse_reflection(raw: str) -> Dict:
        """兼容模型偶尔输出 Markdown 代码块的情况。"""
        match = re.search(r"\{.*\}", raw, re.S)
        if not match:
            raise ValueError("Self-RAG 未返回 JSON")
        data = json.loads(match.group(0))
        for key in ("support", "relevance", "completeness"):
            data[key] = max(0.0, min(1.0, float(data.get(key, 0))))
        data["retry"] = bool(data.get("retry", False))
        data["feedback"] = str(data.get("feedback", ""))[:300]
        return data

    @staticmethod
    def _should_retry(reflection: Dict) -> bool:
        threshold = settings.SELF_RAG_SCORE_THRESHOLD
        scores = [reflection.get(k, 0) for k in ("support", "relevance", "completeness")]
        return bool(reflection.get("retry")) or min(scores) < threshold

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
        """兼容旧调用：默认使用 LightRAG 混合检索。"""
        return self._retrieve_lightrag(question, course_id)[:top_k]

    def _retrieve_lightrag(
        self,
        question: str,
        course_id: Optional[int] = None,
        expanded: bool = False,
    ) -> List[Dict]:
        """
        轻量 LightRAG：
        - local：问题与知识点名称/描述的局部匹配
        - graph：从命中实体沿 Neo4j 关系扩展一跳邻居
        - global：补充课程模块级概要，回答综合性问题
        """
        multiplier = 2 if expanded else 1
        local_k = settings.LIGHTRAG_LOCAL_TOP_K * multiplier
        graph_k = settings.LIGHTRAG_GRAPH_TOP_K * multiplier
        global_k = settings.LIGHTRAG_GLOBAL_TOP_K * multiplier

        local = self._keyword_search(question, course_id, local_k)
        for item in local:
            item["source_type"] = "local"

        graph = self._graph_expand(local, course_id, graph_k)
        global_refs = self._global_module_search(question, course_id, global_k)
        return self._merge_references(local, graph, global_refs)

    def _graph_expand(
        self,
        seeds: List[Dict],
        course_id: Optional[int],
        top_k: int,
    ) -> List[Dict]:
        """沿知识图谱关系扩展一跳邻居，并保留关系类型作为证据。"""
        seed_ids = [s.get("neo4j_id") for s in seeds if s.get("neo4j_id")]
        if not seed_ids:
            return []
        try:
            rows = run_cypher(
                """
                MATCH (seed:KnowledgePoint)-[r]-(neighbor:KnowledgePoint)
                WHERE seed.neo4j_id IN $seed_ids
                  AND ($course_id IS NULL OR neighbor.course_id = $course_id)
                RETURN DISTINCT neighbor.neo4j_id AS neo4j_id,
                       neighbor.name AS name,
                       neighbor.description AS description,
                       type(r) AS relation,
                       seed.name AS connected_from
                LIMIT $limit
                """,
                {"seed_ids": seed_ids, "course_id": course_id, "limit": top_k},
            )
        except Exception:
            return []

        seed_scores = {s.get("name"): float(s.get("score", 0)) for s in seeds}
        refs = []
        for row in rows:
            base = seed_scores.get(row.get("connected_from"), 0.3)
            refs.append({
                "neo4j_id": row.get("neo4j_id"),
                "name": row.get("name", ""),
                "description": row.get("description", ""),
                "relation": row.get("relation", "RELATED_TO"),
                "connected_from": row.get("connected_from", ""),
                "score": round(max(0.15, base * 0.72), 3),
                "source_type": "graph",
            })
        return refs

    def _global_module_search(
        self,
        question: str,
        course_id: Optional[int],
        top_k: int,
    ) -> List[Dict]:
        """检索模块级节点，为概览、比较和学习顺序问题提供全局背景。"""
        broad_terms = ("哪些", "主要", "整体", "结构", "顺序", "路线", "关系", "总结", "概括")
        broad_query = any(term in question for term in broad_terms)
        try:
            if course_id:
                rows = run_cypher(
                    """
                    MATCH (kp:KnowledgePoint {course_id: $course_id})
                    WHERE coalesce(kp.is_module, false) = true OR coalesce(kp.level, 2) < 2
                    RETURN kp.neo4j_id AS neo4j_id, kp.name AS name,
                           kp.description AS description
                    ORDER BY kp.order_index LIMIT $limit
                    """,
                    {"course_id": course_id, "limit": top_k},
                )
            else:
                rows = run_cypher(
                    """
                    MATCH (kp:KnowledgePoint)
                    WHERE coalesce(kp.is_module, false) = true OR coalesce(kp.level, 2) < 2
                    RETURN kp.neo4j_id AS neo4j_id, kp.name AS name,
                           kp.description AS description
                    ORDER BY kp.order_index LIMIT $limit
                    """,
                    {"limit": top_k},
                )
        except Exception:
            return []

        score = 0.42 if broad_query else 0.18
        return [{
            "neo4j_id": row.get("neo4j_id"),
            "name": row.get("name", ""),
            "description": row.get("description", ""),
            "score": score,
            "source_type": "global",
        } for row in rows]

    @staticmethod
    def _merge_references(*groups: List[Dict]) -> List[Dict]:
        """按节点去重，优先保留得分更高、信息更完整的证据。"""
        merged: Dict[str, Dict] = {}
        priority = {"local": 3, "graph": 2, "global": 1}
        for group in groups:
            for ref in group:
                key = ref.get("neo4j_id") or ref.get("name")
                if not key:
                    continue
                current = merged.get(key)
                if current is None or (
                    float(ref.get("score", 0)), priority.get(ref.get("source_type"), 0)
                ) > (
                    float(current.get("score", 0)), priority.get(current.get("source_type"), 0)
                ):
                    merged[key] = ref
        return sorted(merged.values(), key=lambda x: float(x.get("score", 0)), reverse=True)

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

        # 对问题分词；过滤常见虚词和标点，降低噪声。
        stopwords = {"的", "了", "是", "在", "和", "与", "吗", "呢", "什么", "怎么", "如何"}
        keywords = {
            word.strip().lower() for word in jieba.cut(question)
            if word.strip() and word.strip() not in stopwords
            and not re.fullmatch(r"\W+", word.strip())
        }

        # 计算每个节点与问题的匹配分数
        scored = []
        for node in nodes:
            node_text = f"{node.get('name', '')} {node.get('description', '')}"
            node_words = {word.strip().lower() for word in jieba.cut(node_text) if word.strip()}
            overlap = keywords & node_words
            exact_name = bool(node.get("name") and node.get("name", "").lower() in question.lower())
            if overlap or exact_name:
                overlap_score = len(overlap) / max(len(keywords), 1)
                score = min(1.0, overlap_score + (0.45 if exact_name else 0.0))
                scored.append({
                    "neo4j_id": node["neo4j_id"],
                    "name": node.get("name", ""),
                    "description": node.get("description", ""),
                    "score": round(score, 3),
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
            source_label = {
                "local": "局部命中",
                "graph": "图谱邻域",
                "global": "课程模块",
            }.get(ref.get("source_type"), "知识库")
            relation = ""
            if ref.get("relation"):
                relation = (f"\n图谱关系：{ref.get('connected_from', '')}"
                            f" —[{ref['relation']}]— {name}")
            parts.append(
                f"知识点{i}：{name}\n证据类型：{source_label}\n内容：{desc}{relation}\n"
            )

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
