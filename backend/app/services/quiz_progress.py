"""
练习进度回写服务
----------------
根据答题结果更新掌握程度，维护错题本。
"""

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    KnowledgeStatus,
    Question,
    UserKnowledgeProgress,
    WrongQuestion,
)

settings = get_settings()


def apply_quiz_results(
    db: Session,
    user_id: int,
    kp_scores: Dict[int, Dict],
    wrong_question_ids: List[int],
) -> List[Dict]:
    """
    根据各知识点的答题正确率更新学习进度。

    Args:
        kp_scores: {knowledge_point_id: {"correct": 4, "total": 5}}
        wrong_question_ids: 答错的题目 ID 列表

    Returns:
        更新后的进度摘要列表
    """
    threshold = settings.QUIZ_MASTERY_THRESHOLD
    updates = []

    for kp_id, stats in kp_scores.items():
        total = stats["total"]
        correct = stats["correct"]
        accuracy = correct / total if total > 0 else 0.0

        if accuracy >= threshold:
            status = KnowledgeStatus.MASTERED
        elif accuracy > 0:
            status = KnowledgeStatus.IN_PROGRESS
        else:
            status = KnowledgeStatus.IN_PROGRESS

        progress = (
            db.query(UserKnowledgeProgress)
            .filter(
                UserKnowledgeProgress.user_id == user_id,
                UserKnowledgeProgress.knowledge_point_id == kp_id,
            )
            .first()
        )

        if progress:
            progress.status = status
            progress.mastery_level = round(accuracy, 2)
        else:
            progress = UserKnowledgeProgress(
                user_id=user_id,
                knowledge_point_id=kp_id,
                status=status,
                mastery_level=round(accuracy, 2),
            )
            db.add(progress)

        updates.append({
            "knowledge_point_id": kp_id,
            "status": status.value,
            "mastery_level": round(accuracy, 2),
            "accuracy": round(accuracy * 100, 1),
            "mastered": accuracy >= threshold,
        })

    _update_wrong_book(db, user_id, wrong_question_ids, kp_scores)
    db.commit()
    return updates


def _update_wrong_book(
    db: Session,
    user_id: int,
    wrong_question_ids: List[int],
    kp_scores = None,  # type: Optional[Dict[int, Dict]]
):
    """记录错题到错题本，同时将已掌握知识点对应的错题标记为 mastered"""
    threshold = settings.QUIZ_MASTERY_THRESHOLD
    kp_scores = kp_scores or {}

    # 将本次答对的题目对应的知识点中、正确率达标的知识点找出
    mastered_kp_ids: set[int] = set()
    for kp_id, stats in kp_scores.items():
        total = stats["total"]
        correct = stats["correct"]
        accuracy = correct / total if total > 0 else 0.0
        if accuracy >= threshold:
            mastered_kp_ids.add(kp_id)

    # 处理本次答错的题目：加入错题本
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

    # 将已掌握知识点对应的错题标记为 mastered
    if mastered_kp_ids:
        db.query(WrongQuestion).filter(
            WrongQuestion.user_id == user_id,
            WrongQuestion.knowledge_point_id.in_(list(mastered_kp_ids)),
            WrongQuestion.mastered == False,  # noqa: E712
        ).update(
            {"mastered": True},
            synchronize_session=False,
        )
