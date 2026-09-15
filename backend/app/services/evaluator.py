"""
对话式学习评判服务 (功能5)
--------------------------
通过多轮 AI 对话自动评估学生对某个知识点的掌握程度，
并回写 user_knowledge_progress 表。

流程：
    开始 → AI 提问 → 学生回答 → AI 追问/评判 → … → 综合评分 → 更新进度

说明：
  - 会话状态保存在内存中（单机部署足够；重启后丢失未完成会话）。
  - 无 DeepSeek API Key 时返回友好提示，不崩溃。
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import (
    KnowledgePoint, KnowledgeStatus, UserKnowledgeProgress,
)

settings = get_settings()

MAX_ROUNDS = 4  # 最多 4 轮问答后强制给出评判


class EvaluatorService:
    """对话式学习评判器（内存会话存储）。"""

    def __init__(self):
        self._sessions: Dict[str, dict] = {}
        self._ready = bool(settings.DEEPSEEK_API_KEY and
                           settings.DEEPSEEK_API_KEY != "your-deepseek-api-key")

    @property
    def ready(self) -> bool:
        return self._ready

    def start(self, user_id: int, kp: KnowledgePoint) -> dict:
        """开始一轮评判，返回 eval_id 与首个问题。"""
        if not self._ready:
            return {"error": "DeepSeek API Key 未配置，无法进行对话式评判"}

        eval_id = str(uuid.uuid4())
        state = {
            "user_id": user_id,
            "kp_id": kp.id,
            "kp_name": kp.name,
            "kp_desc": kp.description or "",
            "rounds": 0,
            "history": [],  # [{"role": "assistant", "content": ...}, ...]
        }
        question = self._call_llm(self._prompt_question(kp.name, kp.description))
        state["history"].append({"role": "assistant", "content": question})
        state["rounds"] = 1
        self._sessions[eval_id] = state
        return {"eval_id": eval_id, "question": question, "round": 1}

    def reply(self, eval_id: str, answer: str) -> dict:
        """处理学生回答，返回追问或最终评判。"""
        state = self._sessions.get(eval_id)
        if not state:
            return {"error": "评判会话不存在或已过期"}

        state["history"].append({"role": "user", "content": answer})

        # 决定是追问还是评判
        if state["rounds"] < MAX_ROUNDS:
            result = self._call_llm(
                self._prompt_followup(state["kp_name"], state["kp_desc"], state["history"])
            )
            try:
                data = json.loads(result)
            except Exception:
                data = {}
            if data.get("final") or state["rounds"] >= MAX_ROUNDS - 1:
                return self._finalize(eval_id, state)
            question = data.get("question", "请再详细说说你的理解。")
            state["history"].append({"role": "assistant", "content": question})
            state["rounds"] += 1
            return {"eval_id": eval_id, "status": "continue",
                    "round": state["rounds"],
                    "comment": data.get("comment", ""), "question": question}

        return self._finalize(eval_id, state)

    def _finalize(self, eval_id: str, state: dict) -> dict:
        """综合评判并回写进度。"""
        result = self._call_llm(
            self._prompt_final(state["kp_name"], state["kp_desc"], state["history"])
        )
        try:
            data = json.loads(result)
        except Exception:
            data = {}
        score = max(0, min(100, int(data.get("mastery", 0))))
        mastery_level = round(score / 100.0, 2)
        status = self._score_to_status(score)

        # 回写进度
        self._update_progress(state["user_id"], state["kp_id"], status, mastery_level)

        self._sessions.pop(eval_id, None)

        return {
            "status": "final",
            "mastery": score,
            "mastery_level": mastery_level,
            "learning_status": status.value,
            "comment": data.get("comment", ""),
            "weak_points": data.get("weak_points", []),
            "suggestions": data.get("suggestions", []),
        }

    # ---- 进度回写 ----

    @staticmethod
    def _score_to_status(score: int) -> KnowledgeStatus:
        if score >= 80:
            return KnowledgeStatus.MASTERED
        if score >= 30:
            return KnowledgeStatus.IN_PROGRESS
        return KnowledgeStatus.NOT_STARTED

    @staticmethod
    def _update_progress(user_id: int, kp_id: int, status: KnowledgeStatus, level: float):
        db = SessionLocal()
        try:
            progress = (
                db.query(UserKnowledgeProgress)
                .filter(UserKnowledgeProgress.user_id == user_id,
                        UserKnowledgeProgress.knowledge_point_id == kp_id)
                .first()
            )
            if progress:
                progress.status = status
                progress.mastery_level = level
            else:
                db.add(UserKnowledgeProgress(
                    user_id=user_id, knowledge_point_id=kp_id,
                    status=status, mastery_level=level,
                ))
            db.commit()
        finally:
            db.close()

    # ---- 提示词 ----

    @staticmethod
    def _prompt_question(name: str, desc: str) -> str:
        return (
            f"你是教学评估助教。请针对知识点「{name}」向学生提出第 1 个开放性问题，"
            f"用于考察其是否真正理解。知识点内容：{desc or '（无）'}\n"
            "只输出问题本身，不要加任何前缀。"
        )

    @staticmethod
    def _prompt_followup(name: str, desc: str, history: List[dict]) -> str:
        lines = "\n".join(f"{'助教' if m['role']=='assistant' else '学生'}：{m['content']}"
                          for m in history)
        return (
            f"你是教学评估助教，正在评估学生对知识点「{name}」的掌握程度。\n"
            f"知识点内容：{desc or '（无）'}\n\n"
            f"当前对话：\n{lines}\n\n"
            "请判断：是否已能判断学生掌握程度？\n"
            "若信息不足，输出追问问题；若已足够（或已到多轮），输出最终评判。\n"
            "严格输出 JSON：\n"
            '{"final": false, "comment": "简短反馈", "question": "追问问题"}  或\n'
            '{"final": true, "mastery": 0, "comment": "综合评语", '
            '"weak_points": ["薄弱点"], "suggestions": ["建议"]}\n'
            "mastery 为 0-100 的整数。只输出 JSON。"
        )

    @staticmethod
    def _prompt_final(name: str, desc: str, history: List[dict]) -> str:
        lines = "\n".join(f"{'助教' if m['role']=='assistant' else '学生'}：{m['content']}"
                          for m in history)
        return (
            f"你是教学评估助教。请根据以下对话，综合评判学生对知识点「{name}」的掌握程度。\n"
            f"知识点内容：{desc or '（无）'}\n\n"
            f"对话记录：\n{lines}\n\n"
            "严格输出 JSON：\n"
            '{"mastery": 0, "comment": "综合评语", "weak_points": ["薄弱点"], '
            '"suggestions": ["建议"]}\n'
            "mastery 为 0-100 的整数。只输出 JSON。"
        )

    # ---- LLM 调用 ----

    def _call_llm(self, prompt: str) -> str:
        try:
            resp = requests.post(
                f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                         "Content-Type": "application/json"},
                json={
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.4,
                    "max_tokens": 1200,
                },
                timeout=60,
                proxies={"http": None, "https": None},
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return f'{{"final": true, "mastery": 50, "comment": "评判服务异常: {e}"}}'


_evaluator: Optional[EvaluatorService] = None


def get_evaluator() -> EvaluatorService:
    global _evaluator
    if _evaluator is None:
        _evaluator = EvaluatorService()
    return _evaluator
