"""
AI 智能练习 API
---------------
提供自适应出题、答题判分、掌握度回写、错题本等功能。
"""

import json
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models import (
    Course,
    Document,
    DocumentStatus,
    KnowledgePoint,
    LearningBehavior,
    Question,
    QuestionDifficulty,
    QuestionSource,
    QuestionType,
    QuizMode,
    QuizSession,
    QuizSessionQuestion,
    QuizSessionStatus,
    User,
    UserAnswer,
    UserRole,
    WrongQuestion,
)
from app.services.question_generator import get_question_generator
from app.services.quiz_grader import grade_question
from app.services.quiz_progress import apply_quiz_results
from app.services.recommender import LearningPathRecommender

settings = get_settings()
router = APIRouter(prefix="/api/quiz", tags=["AI 智能练习"])
recommender = LearningPathRecommender()


# ============================================================
# 请求 / 响应模型
# ============================================================

class GenerateRequest(BaseModel):
    course_id: int
    mode: QuizMode = QuizMode.ADAPTIVE
    knowledge_point_ids: List[int] = Field(default_factory=list)
    difficulty: QuestionDifficulty = QuestionDifficulty.BASIC
    count: int = Field(default=5, ge=1, le=20, description="每个知识点的题目数量")


class AnswerItem(BaseModel):
    question_id: int
    user_answer: str = Field(default="")


class SubmitRequest(BaseModel):
    answers: List[AnswerItem]


class QuestionOut(BaseModel):
    id: int
    knowledge_point_id: int
    knowledge_point_name: str
    question_type: str
    difficulty: str
    content: str
    options: List[str]
    order_index: int


class SessionOut(BaseModel):
    session_id: int
    course_id: int
    mode: str
    difficulty: str
    total_count: int
    questions: List[QuestionOut]


class AnswerResult(BaseModel):
    question_id: int
    is_correct: bool
    score: float
    correct_answer: str
    explanation: str
    user_answer: str


class SubmitResult(BaseModel):
    session_id: int
    total_count: int
    correct_count: int
    score: float
    mastery_threshold: float
    results: List[AnswerResult]
    progress_updates: List[dict]


# ============================================================
# 辅助函数
# ============================================================

def _get_course_or_404(course_id: int, db: Session) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


def _get_doc_context(course_id: int, db: Session) -> str:
    docs = (
        db.query(Document)
        .filter(
            Document.course_id == course_id,
            Document.status.in_([
                DocumentStatus.PARSED,
                DocumentStatus.EXTRACTED,
            ]),
        )
        .all()
    )
    return "\n".join(d.parsed_content for d in docs if d.parsed_content)


def _resolve_target_kps(
    db: Session,
    course_id: int,
    user_id: int,
    mode: QuizMode,
    knowledge_point_ids: List[int],
    max_kps: int = 3,
) -> List[KnowledgePoint]:
    """根据模式确定本次练习的知识点"""
    if mode == QuizMode.KNOWLEDGE_POINT:
        if not knowledge_point_ids:
            raise HTTPException(status_code=400, detail="请指定知识点 ID")
        kps = (
            db.query(KnowledgePoint)
            .filter(
                KnowledgePoint.course_id == course_id,
                KnowledgePoint.id.in_(knowledge_point_ids),
            )
            .all()
        )
        if not kps:
            raise HTTPException(status_code=404, detail="未找到指定知识点")
        return kps

    # ADAPTIVE：从推荐路径取前 N 个可学知识点
    try:
        path = recommender.recommend_path(course_id, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"无法获取学习推荐: {str(e)}",
        )

    ready = path.get("ready_to_learn") or path.get("recommended_next") or []
    if not ready:
        # 回退：取前 N 个未掌握的知识点
        all_kps = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.course_id == course_id)
            .order_by(KnowledgePoint.order_index)
            .all()
        )
        if not all_kps:
            raise HTTPException(status_code=400, detail="课程暂无知识点，请先提取知识图谱")
        return all_kps[:max_kps]

    # 取前 max_kps 个可学知识点
    neo4j_ids = [kp["id"] for kp in ready[:max_kps]]
    kps = (
        db.query(KnowledgePoint)
        .filter(
            KnowledgePoint.course_id == course_id,
            KnowledgePoint.neo4j_node_id.in_(neo4j_ids),
        )
        .order_by(KnowledgePoint.order_index)
        .all()
    )
    if not kps:
        raise HTTPException(status_code=404, detail="推荐知识点未同步到数据库")
    return kps


async def _create_questions_for_kp(
    db: Session,
    kp: KnowledgePoint,
    course_id: int,
    difficulty: QuestionDifficulty,
    doc_context: str,
    count: int = 5,
) -> List[Question]:
    """为知识点生成并入库题目"""
    generator = get_question_generator()
    raw_questions = await generator.generate_for_knowledge_point(
        kp_name=kp.name,
        kp_description=kp.description or "",
        difficulty=difficulty,
        count=count,
        doc_context=doc_context,
    )

    saved = []
    for raw in raw_questions:
        q = Question(
            course_id=course_id,
            knowledge_point_id=kp.id,
            question_type=QuestionType(raw["type"]),
            difficulty=difficulty,
            content=raw["content"],
            options=json.dumps(raw.get("options", []), ensure_ascii=False),
            correct_answer=raw["correct_answer"],
            explanation=raw.get("explanation", ""),
            source=QuestionSource.AI_GENERATED,
            is_active=True,
        )
        db.add(q)
        saved.append(q)

    db.flush()
    return saved


def _question_to_out(q: Question, kp_name: str, order_index: int) -> QuestionOut:
    options = json.loads(q.options) if q.options else []
    return QuestionOut(
        id=q.id,
        knowledge_point_id=q.knowledge_point_id,
        knowledge_point_name=kp_name,
        question_type=q.question_type.value,
        difficulty=q.difficulty.value,
        content=q.content,
        options=options,
        order_index=order_index,
    )


def _build_session(
    db: Session,
    user_id: int,
    course_id: int,
    mode: QuizMode,
    difficulty: QuestionDifficulty,
    questions: List[Question],
    target_kp_ids: Optional[List[int]] = None,
) -> SessionOut:
    """创建练习会话并关联题目"""
    session = QuizSession(
        user_id=user_id,
        course_id=course_id,
        mode=mode,
        difficulty=difficulty,
        target_kp_ids=json.dumps(target_kp_ids or [q.knowledge_point_id for q in questions]),
        total_count=len(questions),
        status=QuizSessionStatus.IN_PROGRESS,
    )
    db.add(session)
    db.flush()

    # 收集所有涉及的知识点名称
    all_kp_ids = {q.knowledge_point_id for q in questions}
    kp_map: Dict[int, str] = {}
    for kp_id in all_kp_ids:
        kp_obj = db.query(KnowledgePoint).get(kp_id)
        if kp_obj:
            kp_map[kp_id] = kp_obj.name

    question_outs = []
    for idx, q in enumerate(questions):
        db.add(QuizSessionQuestion(
            session_id=session.id,
            question_id=q.id,
            order_index=idx,
        ))
        question_outs.append(
            _question_to_out(q, kp_map.get(q.knowledge_point_id, ""), idx)
        )

    db.commit()

    return SessionOut(
        session_id=session.id,
        course_id=course_id,
        mode=mode.value,
        difficulty=difficulty.value,
        total_count=len(question_outs),
        questions=question_outs,
    )


# ============================================================
# API 端点
# ============================================================

@router.post("/generate", response_model=SessionOut)
async def generate_quiz(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    生成练习会话。

    - adaptive: 基于推荐路径自动选择可学知识点（最多 3 个），总题数由 count 指定
    - knowledge_point: 指定知识点，总题数由 count 指定
    - wrong_book: 直接复用错题本中的题目（最多 count 题），无错题时回退 adaptive
    """
    _get_course_or_404(req.course_id, db)
    total_count = req.count

    # ---- wrong_book 模式：直接取错题本中的题目 ----
    if req.mode == QuizMode.WRONG_BOOK:
        wrong_records = (
            db.query(WrongQuestion)
            .join(Question, WrongQuestion.question_id == Question.id)
            .filter(
                WrongQuestion.user_id == current_user.id,
                WrongQuestion.mastered == False,  # noqa: E712
                Question.course_id == req.course_id,
                Question.is_active == True,  # noqa: E712
            )
            .order_by(WrongQuestion.wrong_count.desc(), WrongQuestion.last_wrong_at.desc())
            .limit(total_count)
            .all()
        )

        if wrong_records:
            all_questions: List[Question] = []
            for wr in wrong_records:
                q = db.query(Question).get(wr.question_id)
                if q:
                    all_questions.append(q)

            if all_questions:
                return _build_session(
                    db, current_user.id, req.course_id, req.mode, req.difficulty,
                    all_questions,
                )

        # 无错题时回退到 adaptive
        req.mode = QuizMode.ADAPTIVE

    # ---- adaptive / knowledge_point 模式 ----
    target_kps = _resolve_target_kps(
        db, req.course_id, current_user.id,
        req.mode, req.knowledge_point_ids,
    )

    # 将 total_count 尽量平均分配到各知识点，每个至少 1 题
    num_kps = len(target_kps)
    if num_kps > total_count:
        # 知识点比题目多：只取前 total_count 个知识点，每个 1 题
        target_kps = target_kps[:total_count]
        kp_counts = [1] * total_count
    else:
        base = total_count // num_kps
        remainder = total_count % num_kps
        kp_counts = [base + 1] * remainder + [base] * (num_kps - remainder)

    doc_context = _get_doc_context(req.course_id, db)
    all_questions: List[Question] = []

    for kp, need_count in zip(target_kps, kp_counts):
        # 优先复用已有 active 题目（随机抽取以避免每次相同）
        existing = (
            db.query(Question)
            .filter(
                Question.knowledge_point_id == kp.id,
                Question.is_active == True,  # noqa: E712
                Question.difficulty == req.difficulty,
            )
            .order_by(Question.created_at.desc())
            .limit(need_count * 3)
            .all()
        )
        if len(existing) >= need_count:
            selected = random.sample(existing, need_count)
            all_questions.extend(selected)
        else:
            all_questions.extend(existing)
            shortage = need_count - len(existing)
            new_qs = await _create_questions_for_kp(
                db, kp, req.course_id, req.difficulty, doc_context, count=shortage,
            )
            all_questions.extend(new_qs[:shortage])

    if not all_questions:
        raise HTTPException(status_code=500, detail="题目生成失败")

    return _build_session(
        db, current_user.id, req.course_id, req.mode, req.difficulty,
        all_questions, [kp.id for kp in target_kps],
    )


@router.get("/session/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取练习会话（不含答案）"""
    session = (
        db.query(QuizSession)
        .filter(
            QuizSession.id == session_id,
            QuizSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="练习会话不存在")

    sqs = (
        db.query(QuizSessionQuestion)
        .filter(QuizSessionQuestion.session_id == session_id)
        .order_by(QuizSessionQuestion.order_index)
        .all()
    )

    question_outs = []
    for sq in sqs:
        q = db.query(Question).get(sq.question_id)
        if not q:
            continue
        kp = db.query(KnowledgePoint).get(q.knowledge_point_id)
        question_outs.append(
            _question_to_out(q, kp.name if kp else "", sq.order_index)
        )

    return SessionOut(
        session_id=session.id,
        course_id=session.course_id,
        mode=session.mode.value,
        difficulty=session.difficulty.value,
        total_count=len(question_outs),
        questions=question_outs,
    )


@router.post("/session/{session_id}/submit", response_model=SubmitResult)
def submit_quiz(
    session_id: int,
    req: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交答案并判分，自动更新掌握程度。

    掌握标准：某知识点正确率 ≥ 90% 则标记为 mastered。
    """
    session = (
        db.query(QuizSession)
        .filter(
            QuizSession.id == session_id,
            QuizSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="练习会话不存在")
    if session.status == QuizSessionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="该练习已提交")

    answer_map = {a.question_id: a.user_answer for a in req.answers}

    sqs = (
        db.query(QuizSessionQuestion)
        .filter(QuizSessionQuestion.session_id == session_id)
        .order_by(QuizSessionQuestion.order_index)
        .all()
    )

    results: List[AnswerResult] = []
    kp_scores: dict = {}
    wrong_ids: List[int] = []
    correct_count = 0

    for sq in sqs:
        q = db.query(Question).get(sq.question_id)
        if not q:
            continue

        user_ans = answer_map.get(q.id, "")
        graded = grade_question(q, user_ans)

        if graded["is_correct"]:
            correct_count += 1
        else:
            wrong_ids.append(q.id)

        kp_id = q.knowledge_point_id
        if kp_id not in kp_scores:
            kp_scores[kp_id] = {"correct": 0, "total": 0}
        kp_scores[kp_id]["total"] += 1
        if graded["is_correct"]:
            kp_scores[kp_id]["correct"] += 1

        db.add(UserAnswer(
            session_id=session_id,
            question_id=q.id,
            user_id=current_user.id,
            user_answer=user_ans,
            is_correct=graded["is_correct"],
            score=graded["score"],
        ))

        results.append(AnswerResult(
            question_id=q.id,
            is_correct=graded["is_correct"],
            score=graded["score"],
            correct_answer=graded["correct_answer"],
            explanation=graded["explanation"],
            user_answer=user_ans,
        ))

    total = len(results)
    score = round(correct_count / total, 2) if total > 0 else 0.0

    session.correct_count = correct_count
    session.score = score
    session.status = QuizSessionStatus.COMPLETED
    session.finished_at = datetime.now(timezone.utc)

    progress_updates = apply_quiz_results(
        db, current_user.id, kp_scores, wrong_ids,
    )

    # 记录学习行为（供推荐增强使用）
    db.add(LearningBehavior(
        user_id=current_user.id,
        course_id=session.course_id,
        knowledge_point_id=None,
        action="quiz",
        duration_seconds=0,
        score=score,
    ))
    db.commit()

    return SubmitResult(
        session_id=session_id,
        total_count=total,
        correct_count=correct_count,
        score=score,
        mastery_threshold=settings.QUIZ_MASTERY_THRESHOLD,
        results=results,
        progress_updates=progress_updates,
    )


@router.get("/wrong-book/{course_id}")
def get_wrong_book(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取错题本列表"""
    _get_course_or_404(course_id, db)

    records = (
        db.query(WrongQuestion)
        .join(Question, WrongQuestion.question_id == Question.id)
        .filter(
            WrongQuestion.user_id == current_user.id,
            WrongQuestion.mastered == False,  # noqa: E712
            Question.course_id == course_id,
        )
        .order_by(WrongQuestion.last_wrong_at.desc())
        .all()
    )

    items = []
    for r in records:
        q = db.query(Question).get(r.question_id)
        kp = db.query(KnowledgePoint).get(r.knowledge_point_id)
        if not q:
            continue
        items.append({
            "wrong_id": r.id,
            "question_id": q.id,
            "knowledge_point_id": r.knowledge_point_id,
            "knowledge_point_name": kp.name if kp else "",
            "content": q.content,
            "question_type": q.question_type.value,
            "wrong_count": r.wrong_count,
            "last_wrong_at": r.last_wrong_at.isoformat() if r.last_wrong_at else "",
        })

    return {"course_id": course_id, "total": len(items), "items": items}


# ============================================================
# 练习历史
# ============================================================

class SessionHistoryItem(BaseModel):
    session_id: int
    mode: str
    difficulty: str
    total_count: int
    correct_count: int
    score: float
    status: str
    started_at: str
    finished_at: Optional[str]


@router.get("/sessions/{course_id}", response_model=List[SessionHistoryItem])
def list_sessions(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取用户在指定课程下的练习历史记录。
    按时间倒序排列，包含每次练习的得分统计。
    """
    _get_course_or_404(course_id, db)

    sessions = (
        db.query(QuizSession)
        .filter(
            QuizSession.user_id == current_user.id,
            QuizSession.course_id == course_id,
        )
        .order_by(QuizSession.started_at.desc())
        .limit(50)
        .all()
    )

    return [
        SessionHistoryItem(
            session_id=s.id,
            mode=s.mode.value if s.mode else "",
            difficulty=s.difficulty.value if s.difficulty else "",
            total_count=s.total_count,
            correct_count=s.correct_count,
            score=s.score,
            status=s.status.value if s.status else "",
            started_at=s.started_at.isoformat() if s.started_at else "",
            finished_at=s.finished_at.isoformat() if s.finished_at else None,
        )
        for s in sessions
    ]


@router.get("/session/{session_id}/review")
def review_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取已完成练习的详细回顾（含答案和解析）。
    与 get_session 不同，此接口返回用户的作答记录和判分结果。
    """
    session = (
        db.query(QuizSession)
        .filter(
            QuizSession.id == session_id,
            QuizSession.user_id == current_user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="练习会话不存在")

    sqs = (
        db.query(QuizSessionQuestion)
        .filter(QuizSessionQuestion.session_id == session_id)
        .order_by(QuizSessionQuestion.order_index)
        .all()
    )

    questions = []
    for sq in sqs:
        q = db.query(Question).get(sq.question_id)
        if not q:
            continue
        kp = db.query(KnowledgePoint).get(q.knowledge_point_id)
        answer = (
            db.query(UserAnswer)
            .filter(
                UserAnswer.session_id == session_id,
                UserAnswer.question_id == q.id,
            )
            .first()
        )
        questions.append({
            "question_id": q.id,
            "knowledge_point_name": kp.name if kp else "",
            "question_type": q.question_type.value,
            "content": q.content,
            "options": json.loads(q.options) if q.options else [],
            "correct_answer": q.correct_answer,
            "explanation": q.explanation or "",
            "user_answer": answer.user_answer if answer else "",
            "is_correct": answer.is_correct if answer else False,
            "order_index": sq.order_index,
        })

    return {
        "session_id": session.id,
        "course_id": session.course_id,
        "mode": session.mode.value if session.mode else "",
        "difficulty": session.difficulty.value if session.difficulty else "",
        "total_count": session.total_count,
        "correct_count": session.correct_count,
        "score": session.score,
        "status": session.status.value if session.status else "",
        "started_at": session.started_at.isoformat() if session.started_at else "",
        "finished_at": session.finished_at.isoformat() if session.finished_at else None,
        "questions": questions,
    }


# ============================================================
# 功能8：教师题库管理
# ============================================================

def _teacher_only(user: User):
    if user.role != UserRole.TEACHER:
        raise HTTPException(status_code=403, detail="仅教师可执行此操作")


class QuestionGenerateRequest(BaseModel):
    course_id: int
    knowledge_point_id: int
    difficulty: QuestionDifficulty = QuestionDifficulty.BASIC
    count: int = Field(default=5, ge=1, le=50)


class QuestionUpdate(BaseModel):
    content: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    difficulty: Optional[QuestionDifficulty] = None
    is_active: Optional[bool] = None


class QuestionReviewRequest(BaseModel):
    question_ids: List[int]
    action: str = "approve"  # approve=启用 / reject=停用


@router.post("/questions/generate")
async def generate_questions_batch(
    req: QuestionGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """教师：AI 批量生成题目（指定知识点 + 数量 + 难度）。"""
    _teacher_only(current_user)
    kp = db.query(KnowledgePoint).filter(
        KnowledgePoint.id == req.knowledge_point_id,
        KnowledgePoint.course_id == req.course_id,
    ).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    doc_context = _get_doc_context(req.course_id, db)
    new_qs = await _create_questions_for_kp(
        db, kp, req.course_id, req.difficulty, doc_context, count=req.count,
    )
    db.commit()

    return {
        "generated": len(new_qs),
        "questions": [
            _question_to_out(q, kp.name, i) for i, q in enumerate(new_qs)
        ],
    }


@router.get("/questions/")
def list_questions(
    course_id: int,
    kp_id: Optional[int] = None,
    difficulty: Optional[QuestionDifficulty] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """题库查询（按课程 + 可选知识点/难度筛选）。"""
    q = db.query(Question).filter(Question.course_id == course_id)
    if kp_id is not None:
        q = q.filter(Question.knowledge_point_id == kp_id)
    if difficulty is not None:
        q = q.filter(Question.difficulty == difficulty)

    questions = q.order_by(Question.created_at.desc()).limit(200).all()
    kp_map = {
        kp.id: kp.name
        for kp in db.query(KnowledgePoint).filter(
            KnowledgePoint.course_id == course_id).all()
    }
    return [
        {
            "id": qq.id,
            "knowledge_point_id": qq.knowledge_point_id,
            "knowledge_point_name": kp_map.get(qq.knowledge_point_id, ""),
            "question_type": qq.question_type.value,
            "difficulty": qq.difficulty.value,
            "content": qq.content,
            "options": json.loads(qq.options) if qq.options else [],
            "correct_answer": qq.correct_answer,
            "explanation": qq.explanation or "",
            "source": qq.source.value,
            "is_active": qq.is_active,
            "created_at": qq.created_at.isoformat() if qq.created_at else "",
        }
        for qq in questions
    ]


@router.put("/questions/{question_id}")
def update_question(
    question_id: int,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """教师：编辑题目。"""
    _teacher_only(current_user)
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    if data.content is not None:
        q.content = data.content
    if data.options is not None:
        q.options = json.dumps(data.options, ensure_ascii=False)
    if data.correct_answer is not None:
        q.correct_answer = data.correct_answer
    if data.explanation is not None:
        q.explanation = data.explanation
    if data.difficulty is not None:
        q.difficulty = data.difficulty
    if data.is_active is not None:
        q.is_active = data.is_active

    # 教师编辑后标记来源
    q.source = QuestionSource.TEACHER_EDITED
    db.commit()
    return {"id": q.id, "message": "题目已更新"}


@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """教师：删除题目及其关联记录。"""
    _teacher_only(current_user)
    q = db.query(Question).filter(Question.id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")

    db.query(UserAnswer).filter(UserAnswer.question_id == question_id).delete()
    db.query(QuizSessionQuestion).filter(
        QuizSessionQuestion.question_id == question_id).delete()
    db.query(WrongQuestion).filter(WrongQuestion.question_id == question_id).delete()
    db.delete(q)
    db.commit()
    return {"message": "题目已删除"}


@router.get("/questions/stats")
def question_stats(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """题目使用统计：被练习次数 / 正确率。"""
    _teacher_only(current_user)
    questions = db.query(Question).filter(Question.course_id == course_id).all()

    # 统计每题的作答情况
    stats = []
    for q in questions:
        answers = db.query(UserAnswer).filter(UserAnswer.question_id == q.id).all()
        attempt_count = len(answers)
        correct_count = sum(1 for a in answers if a.is_correct)
        accuracy = round(correct_count / attempt_count, 2) if attempt_count else 0.0
        stats.append({
            "question_id": q.id,
            "content": q.content[:60],
            "knowledge_point_id": q.knowledge_point_id,
            "attempt_count": attempt_count,
            "correct_count": correct_count,
            "accuracy": accuracy,
            "is_active": q.is_active,
        })

    return {"course_id": course_id, "total": len(stats), "items": stats}


@router.post("/questions/review")
def review_questions(
    req: QuestionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """教师：批量审核题目（启用/停用）。"""
    _teacher_only(current_user)
    target_active = req.action == "approve"
    questions = db.query(Question).filter(Question.id.in_(req.question_ids)).all()
    for q in questions:
        q.is_active = target_active
        q.source = QuestionSource.TEACHER_EDITED
    db.commit()
    return {"message": f"已{'启用' if target_active else '停用'} {len(questions)} 道题目"}
