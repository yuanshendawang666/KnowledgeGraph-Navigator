"""
对话式学习评判 API (功能5)
--------------------------
- POST /api/learning/evaluate/start — 开始评判对话
- POST /api/learning/evaluate/reply — 学生回复，AI 追问 / 评判（最终结果内联返回）
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import User, KnowledgePoint
from app.services.evaluator import get_evaluator

router = APIRouter(prefix="/api/learning/evaluate", tags=["对话式评判"])


class EvaluateStart(BaseModel):
    knowledge_point_id: int


class EvaluateReply(BaseModel):
    eval_id: str
    answer: str = ""


@router.post("/start")
def start_evaluate(
    data: EvaluateStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """开始对某个知识点的对话式掌握度评判。"""
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == data.knowledge_point_id).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    evaluator = get_evaluator()
    result = evaluator.start(current_user.id, kp)
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


@router.post("/reply")
def reply_evaluate(
    data: EvaluateReply,
    current_user: User = Depends(get_current_user),
):
    """提交回答，AI 返回追问或最终评判（最终评判会自动更新学习进度）。"""
    evaluator = get_evaluator()
    result = evaluator.reply(data.eval_id, data.answer)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
