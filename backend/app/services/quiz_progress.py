"""
练习错题记录服务
----------------
练习答题只记录错题，学习进度已改为由 AI 对话评判更新。
"""

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models import (
    Question,
    WrongQuestion,
)


def apply_quiz_results(
    db: Session,
    user_id: int,
    kp_scores: Dict[int, Dict],
    wrong_question_ids: List[int],
) -> List[Dict]:
    """
    记录错题到错题本。

    注意：学习进度已改为由 AI 对话评判（/api/learning/evaluate）更新，
    练习答题不再自动更新掌握程度，只保留错题记录。
    """
    _update_wrong_book(db, user_id, wrong_question_ids)
    db.commit()
    return []


def _update_wrong_book(
    db: Session,
    user_id: int,
    wrong_question_ids: List[int],
):
    """记录错题到错题本。"""
    if wrong_question_ids:
        questions = (
            db.query(Question)
            .filter(Question.id.in_(wrong_question_ids))
            .all()
        )

        for q in questions:
            record = (
                db.query(WrongQuestion)
                .filter(
                    WrongQuestion.user_id == user_id,
                    WrongQuestion.question_id == q.id,
                )
                .first()
            )
            if record:
                record.wrong_count += 1
                record.last_wrong_at = datetime.now(timezone.utc)
                record.mastered = False
            else:
                db.add(WrongQuestion(
                    user_id=user_id,
                    question_id=q.id,
                    knowledge_point_id=q.knowledge_point_id,
                    wrong_count=1,
                ))
