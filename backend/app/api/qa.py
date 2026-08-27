"""
智能问答 API 路由
----------------
提供基于 RAG 的智能问答接口，以及推荐问题生成。

端点：
- POST /api/qa/ask                 — 提交问题，获取 AI 回答
- GET  /api/qa/recommend-questions  — 获取推荐问题列表
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import ChatSession, ChatMessage, User
from app.services.rag import get_rag_service

router = APIRouter(prefix="/api/qa", tags=["智能问答"])


# ============================================================
# 请求 / 响应模型
# ============================================================

class AskRequest(BaseModel):
    """问答请求"""
    course_id: Optional[int] = Field(default=None, description="课程 ID（可选，为空则全局搜索）")
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="学生提出的问题",
    )
    session_id: Optional[int] = Field(
        default=None, description="对话会话 ID（可选，提供则进行多轮对话并持久化）",
    )


class Reference(BaseModel):
    """参考知识点（与 rag 服务 _retrieve 返回结构一致）"""
    neo4j_id: Optional[str] = Field(default=None, description="Neo4j 节点 ID")
    name: str = Field(..., description="知识点名称")
    score: Optional[float] = Field(default=None, description="相关度评分 (0~1)")


# ============================================================
# 端点实现
# ============================================================

@router.post("/ask")
async def ask_question(
    req: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    智能问答接口

    接收学生问题，通过 RAG 流水线检索相关知识点，
    由 DeepSeek 大模型基于课程内容生成回答。

    若提供 session_id，则：
      1. 读取该会话最近的历史消息作为多轮上下文
      2. 将本轮问答持久化到 chat_messages 表
    """
    # ---- 加载会话与历史 ----
    session = None
    history: List[dict] = []
    if req.session_id is not None:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == req.session_id,
                    ChatSession.user_id == current_user.id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        history = [
            {"role": m.role, "content": m.content}
            for m in session.messages[-6:]
        ]

    try:
        rag = get_rag_service()
        result = await rag.ask(
            question=req.question,
            course_id=req.course_id,
            history=history or None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答服务异常: {str(e)}")

    references = result.get("references", [])

    # ---- 持久化消息 ----
    if session is not None:
        import json
        db.add(ChatMessage(
            session_id=session.id, role="user", content=req.question,
        ))
        db.add(ChatMessage(
            session_id=session.id, role="assistant",
            content=result.get("answer", ""),
            references_json=json.dumps(references, ensure_ascii=False),
        ))
        # 自动用首个问题作为会话标题（新消息尚未 flush，不能依赖 session.messages）
        if session.title in ("新对话", ""):
            session.title = req.question[:30]
        from datetime import datetime, timezone
        session.updated_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "answer": result.get("answer", ""),
        "sources": references,
        "suggested_questions": result.get("suggested_questions", []),
        "session_id": session.id if session else None,
    }


@router.get("/recommend-questions")
async def recommend_questions(
    course_id: Optional[int] = Query(default=None, description="课程 ID（可选）"),
    current_user=Depends(get_current_user),
):
    """
    获取推荐问题列表

    根据课程中的重要知识点，自动生成引导学生思考的推荐问题，
    帮助学生发现想要了解的知识点。
    """
    try:
        rag = get_rag_service()
        questions = await rag.recommend_questions(course_id=course_id)
        return questions  # 直接返回字符串列表
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推荐问题生成失败: {str(e)}")
