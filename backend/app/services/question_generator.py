"""
AI 出题服务
-----------
基于 DeepSeek 为知识点自动生成练习题（单选 / 多选 / 判断）。
"""

import json
import random
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.models import QuestionDifficulty, QuestionType

settings = get_settings()

QUESTION_TYPE_LABELS = {
    QuestionType.SINGLE_CHOICE: "单选题",
    QuestionType.MULTIPLE_CHOICE: "多选题",
    QuestionType.TRUE_FALSE: "判断题",
}


class QuestionGenerator:
    """AI 练习题生成器"""

    def __init__(self):
        self._ready = bool(
            settings.DEEPSEEK_API_KEY
            and settings.DEEPSEEK_API_KEY != "your-deepseek-api-key"
        )
        if self._ready:
            self.client = AsyncOpenAI(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                timeout=90.0,
            )
        else:
            self.client = None
        self.model = settings.DEEPSEEK_MODEL
        self.questions_per_kp = settings.QUIZ_QUESTIONS_PER_KP

    async def generate_for_knowledge_point(
        self,
        kp_name: str,
        kp_description: str,
        difficulty: QuestionDifficulty = QuestionDifficulty.BASIC,
        count: Optional[int] = None,
        doc_context: str = "",
    ) -> List[Dict]:
        """
        为一个知识点生成练习题。

        Returns:
            [{"type", "content", "options", "correct_answer", "explanation"}, ...]
        """
        count = count or self.questions_per_kp
        if self._ready:
            result = await self._generate_via_llm(
                kp_name, kp_description, difficulty, count, doc_context
            )
            if result:
                return result[:count]

        return self._generate_fallback(kp_name, kp_description, count)

    async def _generate_via_llm(
        self,
        kp_name: str,
        kp_description: str,
        difficulty: QuestionDifficulty,
        count: int,
        doc_context: str,
    ) -> List[Dict]:
        if difficulty == QuestionDifficulty.ADVANCED:
            diff_instruction = """难度：提高 (ADVANCED)
要求：
- 考察对知识点的深层理解、分析比较和综合应用能力
- 可设计跨知识点的综合题、场景应用题、辨析题
- 选项应有较强的迷惑性，避免显而易见
- 判断题可设计为需要推理才能判断的命题
- 多选题的正确答案应需要仔细甄别才能选出"""
        else:
            diff_instruction = """难度：基础 (BASIC)
要求：
- 考察对知识点的基本概念、定义和核心原理的理解
- 题目应直接围绕知识点内容，不超纲
- 选项应有明确的正确/错误区分
- 适合初次学习该知识点的学生"""

        context_hint = ""
        if doc_context:
            snippet = doc_context[:1500]
            context_hint = f"\n\n参考课件片段：\n{snippet}"

        system_prompt = f"""你是专业的出题专家。请为知识点生成 {count} 道练习题。

{diff_instruction}

题型混合要求：
1. 单选题(single_choice)：4 个选项，仅一个正确
2. 多选题(multiple_choice)：4 个选项，正确答案至少 2 个
3. 判断题(true_false)：options 固定为 ["正确", "错误"]，correct_answer 为 "true" 或 "false"

严格输出 JSON，格式如下：
{{
  "questions": [
    {{
      "type": "single_choice",
      "content": "题干",
      "options": ["A. 选项1", "B. 选项2", "C. 选项3", "D. 选项4"],
      "correct_answer": "A",
      "explanation": "解析：说明为什么选A，以及其他选项错在哪里"
    }},
    {{
      "type": "multiple_choice",
      "content": "题干（标注"多选"）",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct_answer": "A,C",
      "explanation": "解析：说明每个正确选项的理由"
    }},
    {{
      "type": "true_false",
      "content": "判断题干",
      "options": ["正确", "错误"],
      "correct_answer": "true",
      "explanation": "解析：说明判断依据"
    }}
  ]
}}

注意：correct_answer 单选/判断用大写字母或 true/false；多选用逗号分隔字母如 A,C。"""

        user_content = (
            f"知识点：{kp_name}\n"
            f"描述：{kp_description or '暂无描述'}"
            f"{context_hint}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.5,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            raw = json.loads(response.choices[0].message.content)
            return self._normalize_questions(raw.get("questions", []))
        except Exception as e:
            print(f"[QuestionGenerator] LLM 出题失败: {e}")
            return []

    def _normalize_questions(self, questions: List[Dict]) -> List[Dict]:
        """校验并规范化 LLM 输出"""
        valid = []
        for q in questions:
            qtype = q.get("type", "")
            if qtype not in ("single_choice", "multiple_choice", "true_false"):
                continue
            content = (q.get("content") or "").strip()
            if not content:
                continue

            if qtype == "true_false":
                options = ["正确", "错误"]
                answer = str(q.get("correct_answer", "")).lower()
                if answer in ("true", "正确", "对", "是"):
                    correct = "true"
                elif answer in ("false", "错误", "错", "否"):
                    correct = "false"
                else:
                    continue
            else:
                options = q.get("options") or []
                if len(options) < 2:
                    continue
                correct = str(q.get("correct_answer", "")).upper().replace(" ", "")
                if not correct:
                    continue

            valid.append({
                "type": qtype,
                "content": content,
                "options": options,
                "correct_answer": correct,
                "explanation": (q.get("explanation") or "").strip(),
            })
        return valid

    def _generate_fallback(
        self,
        kp_name: str,
        kp_description: str,
        count: int,
    ) -> List[Dict]:
        """无 API Key 时的本地 fallback 题目"""
        desc = kp_description or f"关于{kp_name}的基本概念"
        templates = [
            {
                "type": "single_choice",
                "content": f"以下哪项最能准确描述「{kp_name}」？",
                "options": [
                    f"A. {desc[:40]}",
                    f"B. 与{kp_name}完全无关的概念",
                    f"C. {kp_name}的错误理解",
                    f"D. 以上都不对",
                ],
                "correct_answer": "A",
                "explanation": f"「{kp_name}」的核心含义是：{desc}",
            },
            {
                "type": "true_false",
                "content": f"「{kp_name}」是本章的重要知识点。",
                "options": ["正确", "错误"],
                "correct_answer": "true",
                "explanation": "该知识点已从课程材料中提取，属于重要内容。",
            },
            {
                "type": "multiple_choice",
                "content": f"关于「{kp_name}」，以下哪些说法是正确的？（多选）",
                "options": [
                    f"A. 属于本课程知识图谱中的节点",
                    f"B. {desc[:30]}",
                    f"C. 与{kp_name}完全无关",
                    f"D. 需要先掌握相关先修知识才能更好理解",
                ],
                "correct_answer": "A,B,D",
                "explanation": "A、B、D 均与知识点相关，C 明显错误。",
            },
            {
                "type": "single_choice",
                "content": f"学习「{kp_name}」的主要目的是？",
                "options": [
                    "A. 掌握该概念并能应用",
                    "B. 仅记住名称即可",
                    "C. 无需理解其与其他知识的关系",
                    "D. 跳过直接学习后续内容",
                ],
                "correct_answer": "A",
                "explanation": "学习的目的是理解并掌握知识点。",
            },
            {
                "type": "true_false",
                "content": f"「{kp_name}」的描述为：{desc[:50]}",
                "options": ["正确", "错误"],
                "correct_answer": "true",
                "explanation": "该描述来自课程知识库。",
            },
        ]
        random.shuffle(templates)
        return templates[:count]


_generator: Optional[QuestionGenerator] = None


def get_question_generator() -> QuestionGenerator:
    global _generator
    if _generator is None:
        _generator = QuestionGenerator()
    return _generator
