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

from typing import List, Optional, Any

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

    try:
        result = recommender.recommend_path(course_id, current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"图数据库不可用，无法生成推荐: {str(e)}。请检查 Neo4j 连接配置。",
        )

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


@router.get("/recommend-v2/{course_id}")
def get_recommend_v2(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    增强版个性化推荐（功能1）。

    融合用户画像（专业/年级/学习目标）、学习行为与图谱拓扑，
    返回带「推荐理由 + 置信度 + 预计时长」的推荐列表。
    """
    _get_course_or_404(course_id, db)

    from app.services.recommender_v2 import get_enhanced_recommender
    try:
        return get_enhanced_recommender().recommend_v2(course_id, current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"图数据库不可用，无法生成增强推荐: {str(e)}。请检查 Neo4j 连接配置。",
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

    try:
        result = recommender.recommend_path(course_id, current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"图数据库不可用: {str(e)}。请检查 Neo4j 连接配置。",
        )

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


# ============================================================
# 模块级进度（新增）
# ============================================================

class ModuleProgress(BaseModel):
    id: int
    name: str
    neo4j_node_id: Optional[str]
    level: int
    is_module: bool
    status: str
    mastery_level: float
    children: list = []


@router.get("/module-progress/{course_id}", response_model=List[ModuleProgress])
def get_module_progress(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取课程**模块级别**的学习进度（树状结构）。

    叶子知识点的进度直接从数据库读取，
    模块的进度由其子节点聚合计算：
      - 模块掌握程度 = 所有子孙叶子的平均值
      - 模块状态：全掌握→mastered, 有进行中→in_progress, 全未开始→not_started
    """
    _get_course_or_404(course_id, db)

    def serialize(modules):
        result = []
        for m in modules:
            item = {
                "id": m["id"], "name": m["name"],
                "neo4j_node_id": m.get("neo4j_node_id"),
                "level": m.get("level", 0), "is_module": m.get("is_module", True),
                "status": m["status"], "mastery_level": m["mastery_level"],
                "children": serialize(m.get("children", [])),
            }
            result.append(item)
        return result

    tree = recommender.calculate_module_progress(course_id, current_user.id)
    return serialize(tree)


# ============================================================
# 学习方法推荐（AI 生成）
# ============================================================

@router.get("/study-methods/{course_id}")
async def get_study_methods(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    根据用户学习进度与画像，推荐具体可执行的学习方法。

    返回：{"summary": "...", "methods": [{"title", "description", "reason"}, ...]}
    """
    course = _get_course_or_404(course_id, db)

    from app.core.config import get_settings
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY in ("your-deepseek-api-key", ""):
        raise HTTPException(status_code=503, detail="DeepSeek API Key 未配置")

    # 叶子知识点及用户进度
    kps = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.course_id == course_id, KnowledgePoint.level == 2)
        .all()
    )
    kp_ids = [k.id for k in kps]
    progress = (
        db.query(UserKnowledgeProgress)
        .filter(
            UserKnowledgeProgress.user_id == current_user.id,
            UserKnowledgeProgress.knowledge_point_id.in_(kp_ids),
        )
        .all()
    ) if kp_ids else []
    progress_map = {p.knowledge_point_id: p for p in progress}

    total = len(kps)
    mastered = sum(
        1 for k in kps
        if (progress_map.get(k.id).mastery_level if progress_map.get(k.id) else 0) >= 0.9
    )
    pct = round(mastered / total * 100, 1) if total else 0.0
    weak_kps = [
        k.name for k in kps
        if (progress_map.get(k.id).mastery_level if progress_map.get(k.id) else 0) < 0.6
    ]

    profile_parts = []
    if current_user.major:
        profile_parts.append(f"专业：{current_user.major}")
    if current_user.grade:
        profile_parts.append(f"年级：{current_user.grade}")
    if current_user.learning_goal:
        profile_parts.append(f"学习目标：{current_user.learning_goal}")
    profile = "，".join(profile_parts) if profile_parts else "（未填写画像）"
    weak_text = "、".join(weak_kps[:5]) if weak_kps else "无（整体掌握良好）"

    prompt = f"""你是学习策略专家。请根据以下学生信息，推荐 3~5 个具体、可操作的学习方法。

课程：{course.title}
学习进度：已掌握 {mastered}/{total} 个知识点（{pct}%）
薄弱知识点：{weak_text}
用户画像：{profile}

请严格按以下 Markdown 格式输出（不要输出 JSON，不要多余内容；「方法名」「做法」「理由」三处请替换为实际内容，不要照抄这些占位词）：

总体建议：（一句话）

### 这里是方法名称
- 做法：这里写具体怎么做
- 理由：这里写为什么适合

每个方法之间留一个空行，共 3~5 个方法。"""

    import re
    import time
    import requests

    def _parse(content: str):
        summary_m = re.search(r'总体建议[：:]\s*(.+)', content)
        summary = summary_m.group(1).strip() if summary_m else ""
        methods = []
        pattern = r'###\s*([^\n]+)\n- 做法[：:]\s*([\s\S]*?)\n- 理由[：:]\s*([\s\S]*?)(?=\n###|$)'
        for m in re.finditer(pattern, content):
            methods.append({
                "title": m.group(1).strip().strip('"“”'),
                "description": m.group(2).strip(),
                "reason": m.group(3).strip(),
            })
        if not methods:
            raise ValueError("未解析到学习方法")
        return {"summary": summary, "methods": methods}

    def _request_once():
        resp = requests.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": settings.DEEPSEEK_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.5, "max_tokens": 1500},
            timeout=60, proxies={"http": None, "https": None},
        )
        content = resp.json()["choices"][0]["message"]["content"].strip()
        return _parse(content)

    for attempt in range(3):  # 最多请求三次，AI 偶发空返回/格式异常时重试
        try:
            return _request_once()
        except Exception as e:
            if attempt < 2:
                time.sleep(1)  # 间隔后重试，缓解偶发空返回
            else:
                print(f"[StudyMethods] 三次解析失败，使用默认方法: {e}")

    # 容错：AI 持续输出异常时返回默认学习方法，避免 500
    return {
        "summary": "建议结合课程进度，采用主动回忆、间隔重复和针对性练习相结合的方式学习。",
        "methods": [
            {"title": "主动回忆法", "description": "合上教材，用自己的话复述每个知识点的核心概念，再对照原文查漏补缺。", "reason": "有效暴露理解盲区，加深记忆"},
            {"title": "间隔重复法", "description": "对已学知识点按 1 天、3 天、7 天的间隔复习，巩固长期记忆。", "reason": "防止遗忘曲线导致的快速遗忘"},
            {"title": "针对性练习", "description": "优先做薄弱知识点的练习题，用智能练习模块巩固。", "reason": "集中攻克薄弱环节，提升效率"},
        ],
    }
