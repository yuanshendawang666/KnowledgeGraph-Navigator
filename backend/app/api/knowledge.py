"""
知识点详情 API (功能7)
----------------------
提供独立的知识点详情聚合接口：基本信息 + 1 跳邻接子图 + 学习状态
+ 关联文档 + 相关笔记，以及按需生成的 AI 讲解内容（讲解/例题/误区）。
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.core.database import get_db, run_cypher
from app.models import (
    User, KnowledgePoint, UserKnowledgeProgress, Document, Note,
)

router = APIRouter(prefix="/api/knowledge", tags=["知识点详情"])

settings = get_settings()


# ============================================================
# 响应模型
# ============================================================

class NeighborOut(BaseModel):
    id: int = 0
    neo4j_id: str = ""
    name: str = ""
    relation: str = ""
    direction: str = "out"  # out: 当前节点指向邻居, in: 邻居指向当前节点


class NoteOut(BaseModel):
    id: int
    user_id: int
    username: str = ""
    title: str
    content: str
    is_public: bool
    created_at: str


class KnowledgeDetailOut(BaseModel):
    id: int
    name: str
    description: str
    neo4j_node_id: Optional[str]
    level: int
    is_module: bool
    parent_id: Optional[int]
    course_id: int
    course_title: str
    status: str = "not_started"
    mastery_level: float = 0.0
    neighbors: List[NeighborOut] = []
    documents: List[dict] = []
    notes: List[NoteOut] = []


# ============================================================
# 辅助函数
# ============================================================

def _get_kp_or_404(kp_id: int, db: Session) -> KnowledgePoint:
    kp = db.query(KnowledgePoint).filter(KnowledgePoint.id == kp_id).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")
    return kp


def _get_neighbors(kp: KnowledgePoint) -> List[NeighborOut]:
    """从 Neo4j 获取该知识点的 1 跳邻居（含关系类型与方向）。"""
    if not kp.neo4j_node_id:
        return []
    try:
        out_rows = run_cypher(
            """
            MATCH (a:KnowledgePoint {neo4j_id: $id})-[r]->(b:KnowledgePoint)
            RETURN b.neo4j_id AS neo4j_id, b.name AS name, type(r) AS relation
            """,
            {"id": kp.neo4j_node_id},
        )
        in_rows = run_cypher(
            """
            MATCH (a:KnowledgePoint)-[r]->(b:KnowledgePoint {neo4j_id: $id})
            RETURN a.neo4j_id AS neo4j_id, a.name AS name, type(r) AS relation
            """,
            {"id": kp.neo4j_node_id},
        )
    except Exception:
        return []

    neighbors: List[NeighborOut] = []
    seen = set()
    for row in out_rows:
        if row["neo4j_id"] not in seen:
            seen.add(row["neo4j_id"])
            neighbors.append(NeighborOut(
                neo4j_id=row["neo4j_id"], name=row["name"],
                relation=row["relation"], direction="out",
            ))
    for row in in_rows:
        if row["neo4j_id"] not in seen:
            seen.add(row["neo4j_id"])
            neighbors.append(NeighborOut(
                neo4j_id=row["neo4j_id"], name=row["name"],
                relation=row["relation"], direction="in",
            ))
    return neighbors


# ============================================================
# 端点
# ============================================================

@router.get("/{kp_id}", response_model=KnowledgeDetailOut)
def get_knowledge_detail(
    kp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取知识点详情（聚合基本信息、学习状态、邻接子图、关联文档、笔记）。"""
    kp = _get_kp_or_404(kp_id, db)

    # 学习进度
    progress = (
        db.query(UserKnowledgeProgress)
        .filter(
            UserKnowledgeProgress.user_id == current_user.id,
            UserKnowledgeProgress.knowledge_point_id == kp.id,
        )
        .first()
    )

    # 关联文档（当前知识提取未做 doc→kp 精确映射，这里返回课程级文档）
    documents = (
        db.query(Document)
        .filter(Document.course_id == kp.course_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    doc_list = [
        {"id": d.id, "filename": d.filename, "status": d.status.value if d.status else ""}
        for d in documents
    ]

    # 相关笔记（自己的 + 公开的）
    notes = (
        db.query(Note)
        .filter(
            Note.knowledge_point_id == kp.id,
            (Note.user_id == current_user.id) | (Note.is_public == True),  # noqa: E712
        )
        .order_by(Note.updated_at.desc())
        .all()
    )
    note_list = [
        NoteOut(
            id=n.id, user_id=n.user_id,
            username=n.user.username if n.user else "",
            title=n.title, content=n.content, is_public=n.is_public,
            created_at=n.created_at.isoformat() if n.created_at else "",
        )
        for n in notes
    ]

    return KnowledgeDetailOut(
        id=kp.id,
        name=kp.name,
        description=kp.description or "",
        neo4j_node_id=kp.neo4j_node_id,
        level=kp.level or 2,
        is_module=kp.is_module or False,
        parent_id=kp.parent_id,
        course_id=kp.course_id,
        course_title=kp.course.title if kp.course else "",
        status=progress.status.value if progress else "not_started",
        mastery_level=progress.mastery_level if progress else 0.0,
        neighbors=_get_neighbors(kp),
        documents=doc_list,
        notes=note_list,
    )


class AIContentOut(BaseModel):
    explanation: str = ""
    examples: List[str] = []
    pitfalls: List[str] = []


@router.post("/{kp_id}/ai-content", response_model=AIContentOut)
async def generate_ai_content(
    kp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI 生成知识点讲解内容（详细讲解 / 典型例题 / 常见误区）。
    按需调用 DeepSeek，不缓存。
    """
    kp = _get_kp_or_404(kp_id, db)

    if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY in ("your-deepseek-api-key", ""):
        raise HTTPException(status_code=503, detail="DeepSeek API Key 未配置")

    import json
    import requests

    prompt = f"""你是资深教师。请针对以下知识点生成结构化讲解内容，严格输出 JSON：

{{
  "explanation": "详细讲解（150-300字，分点说明，用 Markdown 无序列表）",
  "examples": ["典型例题1", "典型例题2", "典型例题3"],
  "pitfalls": ["常见误区1", "常见误区2"]
}}

知识点名称：{kp.name}
知识点描述：{kp.description or '（无）'}

只输出 JSON，不要加任何前缀或代码块标记。"""

    try:
        resp = requests.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": settings.DEEPSEEK_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.5,
                "max_tokens": 1500,
                "response_format": {"type": "json_object"},
            },
            timeout=60,
            proxies={"http": None, "https": None},
        )
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 内容生成失败: {e}")

    return AIContentOut(
        explanation=data.get("explanation", ""),
        examples=data.get("examples", []),
        pitfalls=data.get("pitfalls", []),
    )
