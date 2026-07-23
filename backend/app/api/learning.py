"""
学习进度追踪与个性化推荐 API 路由 (功能 3 & 4)
----------------------------------------------
提供学习进度管理和个性化学习路径推荐。

端点：
# 学习进度追踪 (功能 3)
- GET    /api/learning/progress/{course_id}   — 获取用户在某课程的学习进度
- POST   /api/learning/progress              — 更新知识点学习状态
- GET    /api/learning/stats/{course_id}     — 获取课程学习统计

# 个性化推荐 (功能 4)
- GET    /api/learning/recommend/{course_id}  — 获取个性化学习路径推荐
- GET    /api/learning/next/{course_id}       — 获取下一个推荐学习的知识点
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import (
    User, Course, KnowledgePoint, UserKnowledgeProgress,
    KnowledgeStatus,
)
from app.api.auth import get_current_user
from app.services.recommender import LearningPathRecommender

router = APIRouter(prefix="/api/learning", tags=["学习进度与推荐"])

recommender = LearningPathRecommender()


# ---- 请求/响应模型 ----

class ProgressUpdate(BaseModel):
    knowledge_point_id: int = Field(..., description="知识点 ID (SQLite)")
    status: KnowledgeStatus = Field(..., description="学习状态")
    mastery_level: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="掌握程度 0.0~1.0"
    )


class ProgressRecord(BaseModel):
    knowledge_point_id: int
    knowledge_point_name: str
    neo4j_node_id: Optional[str]
    status: str
    mastery_level: float
    updated_at: str


class CourseProgress(BaseModel):
    course_id: int
    course_title: str
    total_points: int
    mastered_count: int
    in_progress_count: int
    not_started_count: int
    progress_percentage: float
    records: List[ProgressRecord]


class CourseStats(BaseModel):
    course_id: int
    course_title: str
    total_points: int
    mastered_count: int
    in_progress_count: int
    not_started_count: int
    progress_percentage: float


class RecommendedPath(BaseModel):
    course_id: int
    total_count: int
    mastered_count: int
    progress_percentage: float
    all_knowledge_points: list
    mastered_ids: list
    in_progress_ids: list
    ready_to_learn: list
    recommended_next: list


class NextRecommendation(BaseModel):
    course_id: int
    recommended_points: list
    message: str


# ---- 辅助函数 ----

def _get_course_or_404(course_id: int, db: Session) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


# ============================================================
# 功能 3: 学习进度追踪
# ============================================================

@router.get("/progress/{course_id}", response_model=CourseProgress)
def get_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户在指定课程的学习进度。
    包含每个知识点的状态和整体统计。
    """
    course = _get_course_or_404(course_id, db)

    # 获取课程所有知识点
    kps = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.course_id == course_id)
        .order_by(KnowledgePoint.order_index)
        .all()
    )

    if not kps:
        return CourseProgress(
            course_id=course_id,
            course_title=course.title,
            total_points=0,
            mastered_count=0,
            in_progress_count=0,
            not_started_count=0,
            progress_percentage=0.0,
            records=[],
        )

    # 获取用户的学习进度记录
    kp_ids = [kp.id for kp in kps]
    progress_records = (
        db.query(UserKnowledgeProgress)
        .filter(
            UserKnowledgeProgress.user_id == current_user.id,
            UserKnowledgeProgress.knowledge_point_id.in_(kp_ids),
        )
        .all()
    )

    progress_map = {
        p.knowledge_point_id: p for p in progress_records
    }

    # 构建响应
    records = []
    mastered = 0
    in_progress = 0
    not_started = 0

    for kp in kps:
        progress = progress_map.get(kp.id)
        status = progress.status if progress else KnowledgeStatus.NOT_STARTED
        mastery = progress.mastery_level if progress else 0.0
        updated = (
            progress.updated_at.isoformat()
            if progress and progress.updated_at
            else ""
        )

        if status == KnowledgeStatus.MASTERED:
            mastered += 1
        elif status == KnowledgeStatus.IN_PROGRESS:
            in_progress += 1
        else:
            not_started += 1

        records.append(ProgressRecord(
            knowledge_point_id=kp.id,
            knowledge_point_name=kp.name,
            neo4j_node_id=kp.neo4j_node_id,
            status=status.value,
            mastery_level=mastery,
            updated_at=updated,
        ))

    total = len(kps)
    progress_pct = round(
        ((mastered + in_progress * 0.5) / total * 100) if total > 0 else 0.0,
        1,
    )

    return CourseProgress(
        course_id=course_id,
        course_title=course.title,
        total_points=total,
        mastered_count=mastered,
        in_progress_count=in_progress,
        not_started_count=not_started,
        progress_percentage=progress_pct,
        records=records,
    )


@router.post("/progress")
def update_progress(
    data: ProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新用户对某个知识点的学习状态。

    支持的操作：
    - 标记为"学习中" (in_progress)
    - 标记为"已掌握" (mastered)
    - 重置为"未开始" (not_started)
    """
    # 验证知识点存在
    kp = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.id == data.knowledge_point_id)
        .first()
    )
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 查找或创建进度记录
    progress = (
        db.query(UserKnowledgeProgress)
        .filter(
            UserKnowledgeProgress.user_id == current_user.id,
            UserKnowledgeProgress.knowledge_point_id == data.knowledge_point_id,
        )
        .first()
    )

    if progress:
        # 更新已有记录
        progress.status = data.status
        progress.mastery_level = data.mastery_level
    else:
        # 创建新记录
        progress = UserKnowledgeProgress(
            user_id=current_user.id,
            knowledge_point_id=data.knowledge_point_id,
            status=data.status,
            mastery_level=data.mastery_level,
        )
        db.add(progress)

    db.commit()
    db.refresh(progress)

    return {
        "message": "学习进度更新成功",
        "knowledge_point_id": data.knowledge_point_id,
        "knowledge_point_name": kp.name,
        "status": progress.status.value,
        "mastery_level": progress.mastery_level,
    }


@router.post("/progress/batch")
def batch_update_progress(
    updates: List[ProgressUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    批量更新多个知识点的学习状态。
    适用于一次性标记多个知识点。
    """
    results = []

    for data in updates:
        kp = (
            db.query(KnowledgePoint)
            .filter(KnowledgePoint.id == data.knowledge_point_id)
            .first()
        )
        if not kp:
            continue

        progress = (
            db.query(UserKnowledgeProgress)
            .filter(
                UserKnowledgeProgress.user_id == current_user.id,
                UserKnowledgeProgress.knowledge_point_id == data.knowledge_point_id,
            )
            .first()
        )

        if progress:
            progress.status = data.status
            progress.mastery_level = data.mastery_level
        else:
            progress = UserKnowledgeProgress(
                user_id=current_user.id,
                knowledge_point_id=data.knowledge_point_id,
                status=data.status,
                mastery_level=data.mastery_level,
            )
            db.add(progress)

        results.append({
            "knowledge_point_id": data.knowledge_point_id,
            "knowledge_point_name": kp.name,
            "status": data.status.value,
        })

    db.commit()

    return {
        "message": f"成功更新 {len(results)} 个知识点的学习状态",
        "updated": results,
    }


@router.get("/stats/{course_id}", response_model=CourseStats)
def get_stats(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取课程的学习统计概览。
    包括总知识点数、已掌握数、进度百分比等。
    """
    course = _get_course_or_404(course_id, db)

    kps = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.course_id == course_id)
        .all()
    )
    kp_ids = [kp.id for kp in kps]

    total = len(kps)
    if total == 0:
        return CourseStats(
            course_id=course_id,
            course_title=course.title,
            total_points=0,
            mastered_count=0,
            in_progress_count=0,
            not_started_count=0,
            progress_percentage=0.0,
        )

    progress_records = (
        db.query(UserKnowledgeProgress)
        .filter(
            UserKnowledgeProgress.user_id == current_user.id,
            UserKnowledgeProgress.knowledge_point_id.in_(kp_ids),
        )
        .all()
    )

    status_counts = {p.status for p in progress_records}
    mastered = sum(
        1 for p in progress_records
        if p.status == KnowledgeStatus.MASTERED
    )
    in_progress = sum(
        1 for p in progress_records
        if p.status == KnowledgeStatus.IN_PROGRESS
    )
    not_started = total - mastered - in_progress

    progress_pct = round(
        ((mastered + in_progress * 0.5) / total * 100), 1
    )

    return CourseStats(
        course_id=course_id,
        course_title=course.title,
        total_points=total,
        mastered_count=mastered,
        in_progress_count=in_progress,
        not_started_count=not_started,
        progress_percentage=progress_pct,
    )


# ============================================================
# 功能 4: 个性化学习路径推荐
# ============================================================

@router.get("/recommend/{course_id}", response_model=RecommendedPath)
def get_recommended_path(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取个性化学习路径推荐。

    基于知识图谱的拓扑排序和用户当前的学习进度，
    返回完整的学习路径和当前推荐学习的知识点。

    推荐逻辑：
    1. 对课程的知识图谱进行拓扑排序（按先修依赖）
    2. 排除用户已掌握的知识点
    3. 找出所有先修条件已满足的"可学"知识点
    4. 推荐排名最前的 5 个
    """
    _get_course_or_404(course_id, db)

    result = recommender.recommend_path(course_id, current_user.id)

    return RecommendedPath(
        course_id=course_id,
        total_count=result["total_count"],
        mastered_count=result["mastered_count"],
        progress_percentage=result["progress_percentage"],
        all_knowledge_points=result["all_knowledge_points"],
        mastered_ids=result["mastered_ids"],
        in_progress_ids=result["in_progress_ids"],
        ready_to_learn=result["ready_to_learn"],
        recommended_next=result["recommended_next"],
    )


@router.get("/next/{course_id}", response_model=NextRecommendation)
def get_next_recommendation(
    course_id: int,
    count: int = Query(default=3, ge=1, le=10, description="推荐数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取下一个推荐学习的知识点（简化版）。

    返回最适合用户当前学习的 N 个知识点，
    基于：所有先修条件已满足 且 用户尚未掌握。
    """
    _get_course_or_404(course_id, db)

    result = recommender.recommend_path(course_id, current_user.id)
    ready = result["ready_to_learn"][:count]

    if not ready:
        # 所有知识点都已掌握或正在学习中
        total = result["total_count"]
        mastered = result["mastered_count"]
        if mastered >= total and total > 0:
            message = "🎉 恭喜！你已完成本课程所有知识点的学习！"
        else:
            message = "当前没有可直接学习的知识点，请先完成先修知识点"
    else:
        names = [kp["label"] for kp in ready]
        message = f"推荐学习：{' → '.join(names)}"

    return NextRecommendation(
        course_id=course_id,
        recommended_points=ready,
        message=message,
    )
