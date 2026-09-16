"""
课程与图谱管理 API 路由 (功能 2)
---------------------------------
提供课程的完整生命周期管理以及知识图谱的构建和查询。

端点：
- POST   /api/courses               — 创建课程
- GET    /api/courses               — 获取课程列表
- GET    /api/courses/{id}          — 获取课程详情
- PUT    /api/courses/{id}          — 更新课程
- DELETE /api/courses/{id}          — 删除课程
- POST   /api/courses/{id}/upload   — 上传文档
- POST   /api/courses/{id}/extract  — 触发知识提取
- GET    /api/courses/{id}/graph    — 获取课程知识图谱
- DELETE /api/courses/{id}/graph    — 清除课程知识图谱
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import (
    User, Course, KnowledgePoint, KnowledgeRelation, Document,
    DocumentStatus, UserRole, RelationType, ExtractionJob, GraphSyncState,
)
from app.api.auth import get_current_user
from app.services.parser import DocumentParser
from app.services.extractor import KnowledgeExtractor
from app.services.graph_ops import GraphOperations
from app.services.graph_sync import mark_pending, sync_course

settings = get_settings()
router = APIRouter(prefix="/api/courses", tags=["课程与图谱管理"])

graph_ops = GraphOperations()


def require_owner(course_id, db, user):
    course = _get_course_or_404(course_id, db)
    if user.role != UserRole.TEACHER or course.teacher_id != user.id:
        raise HTTPException(403, "仅课程教师可操作")
    return course


@router.post('/{course_id}/extract', status_code=202)
def enqueue_extraction(course_id: int, db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    from sqlalchemy import text
    require_owner(course_id, db, current_user)
    db.commit()
    db.execute(text('BEGIN IMMEDIATE'))
    job = db.query(ExtractionJob).filter(ExtractionJob.course_id == course_id,
        ExtractionJob.status.in_(['queued', 'running'])).first()
    if not job:
        job = ExtractionJob(id=uuid.uuid4().hex, course_id=course_id, user_id=current_user.id)
        db.add(job)
    db.commit()
    return {'job_id': job.id, 'status': job.status}


@router.get('/{course_id}/extract/{job_id}')
def extraction_status(course_id: int, job_id: str, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    import json
    require_owner(course_id, db, current_user)
    job = db.query(ExtractionJob).filter_by(id=job_id, course_id=course_id).first()
    if not job:
        raise HTTPException(404, '任务不存在')
    state = db.get(GraphSyncState, course_id)
    return {'job_id': job.id, 'status': job.status, 'error': job.error,
            'result': json.loads(job.result or '{}'),
            'graph_sync': state.status if state else 'pending'}


@router.post('/{course_id}/graph/sync')
def retry_graph_sync(course_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    require_owner(course_id, db, current_user)
    mark_pending(db, course_id)
    db.commit()
    status = sync_course(db, course_id)
    return {'status': status}


class RelationInput(BaseModel):
    source_kp_id: int
    target_kp_id: int
    relation_type: RelationType


def validate_relation(data, course_id, db, exclude_id=None):
    source, target = db.get(KnowledgePoint, data.source_kp_id), db.get(KnowledgePoint, data.target_kp_id)
    if not source or not target or source.course_id != course_id or target.course_id != course_id:
        raise HTTPException(400, '关系两端必须属于当前课程')
    if source.id == target.id:
        raise HTTPException(400, '不能连接到自身')
    rows = db.query(KnowledgeRelation).filter_by(course_id=course_id).all()
    for row in rows:
        if row.id != exclude_id and (row.source_kp_id, row.target_kp_id, row.relation_type) == (
                source.id, target.id, data.relation_type):
            raise HTTPException(409, '关系已存在')
    if data.relation_type in (RelationType.PART_OF, RelationType.PREREQUISITE):
        adjacency = {}
        for r in rows:
            if r.id != exclude_id and r.relation_type == data.relation_type:
                adjacency.setdefault(r.source_kp_id, []).append(r.target_kp_id)
        if data.relation_type == RelationType.PART_OF:
            for p in db.query(KnowledgePoint).filter_by(course_id=course_id).all():
                if p.parent_id and p.id != source.id:
                    adjacency.setdefault(p.id, []).append(p.parent_id)
        pending, seen = [target.id], set()
        while pending:
            node = pending.pop()
            if node == source.id:
                raise HTTPException(400, '该关系会形成循环')
            if node not in seen:
                seen.add(node)
                pending.extend(adjacency.get(node, []))
    return source, target


@router.get('/{course_id}/relations')
def list_relations(course_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_owner(course_id, db, current_user)
    return [dict(id=r.id, source_kp_id=r.source_kp_id, target_kp_id=r.target_kp_id,
                 relation_type=r.relation_type.value)
            for r in db.query(KnowledgeRelation).filter_by(course_id=course_id).all()]


def save_relation(course_id, data, db, relation=None):
    source, target = validate_relation(data, course_id, db, relation.id if relation else None)
    if relation and relation.relation_type == RelationType.PART_OF:
        old = db.get(KnowledgePoint, relation.source_kp_id)
        if old and old.parent_id == relation.target_kp_id:
            old.parent_id = None
    if data.relation_type == RelationType.PART_OF:
        # 同一子节点只能有一个父节点。
        db.query(KnowledgeRelation).filter(KnowledgeRelation.course_id == course_id,
            KnowledgeRelation.source_kp_id == source.id, KnowledgeRelation.relation_type == RelationType.PART_OF,
            KnowledgeRelation.id != (relation.id if relation else -1)).delete(synchronize_session=False)
        source.parent_id = target.id
    if relation is None:
        relation = KnowledgeRelation(course_id=course_id)
        db.add(relation)
    for key, value in data.model_dump().items():
        setattr(relation, key, value)
    mark_pending(db, course_id)
    db.commit()
    return {'id': relation.id, 'graph_sync': sync_course(db, course_id)}


@router.post('/{course_id}/relations')
def create_relation(course_id: int, data: RelationInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_owner(course_id, db, current_user)
    return save_relation(course_id, data, db)


@router.put('/{course_id}/relations/{relation_id}')
def update_relation(course_id: int, relation_id: int, data: RelationInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_owner(course_id, db, current_user)
    row = db.query(KnowledgeRelation).filter_by(id=relation_id, course_id=course_id).first()
    if not row:
        raise HTTPException(404, '关系不存在')
    return save_relation(course_id, data, db, row)


@router.delete('/{course_id}/relations/{relation_id}')
def delete_relation(course_id: int, relation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    require_owner(course_id, db, current_user)
    row = db.query(KnowledgeRelation).filter_by(id=relation_id, course_id=course_id).first()
    if not row:
        raise HTTPException(404, '关系不存在')
    if row.relation_type == RelationType.PART_OF:
        kp = db.get(KnowledgePoint, row.source_kp_id)
        if kp.parent_id == row.target_kp_id:
            kp.parent_id = None
    db.delete(row)
    mark_pending(db, course_id)
    db.commit()
    return {'graph_sync': sync_course(db, course_id)}


# ---- 请求/响应模型 ----

class CourseCreate(BaseModel):
    title: str
    description: str = ""


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class KnowledgePointItem(BaseModel):
    id: int
    neo4j_node_id: str
    name: str
    description: str
    order_index: int
    level: int = 2
    is_module: bool = False

    class Config:
        from_attributes = True


class CourseResponse(BaseModel):
    id: int
    title: str
    description: str
    teacher_id: int
    created_at: str
    updated_at: str
    knowledge_point_count: int = 0
    document_count: int = 0
    knowledge_points: List[KnowledgePointItem] = []

    class Config:
        from_attributes = True


class GraphResponse(BaseModel):
    nodes: list
    edges: list
    tree_edges: list = []
    cross_edges: list = []
    tree: list = []


class ExtractResult(BaseModel):
    knowledge_points_count: int
    relations_count: int
    knowledge_points: list
    relations: list


# ---- 辅助函数 ----

def _teacher_only(user: User):
    """检查用户是否为教师角色"""
    if user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=403,
            detail="仅教师用户可执行此操作",
        )


def _get_course_or_404(course_id: int, db: Session) -> Course:
    """根据 ID 获取课程，不存在则返回 404"""
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="课程不存在")
    return course


def _build_course_response(course: Course, db: Session) -> dict:
    """构建包含统计信息的课程响应"""
    kps = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.course_id == course.id)
        .order_by(KnowledgePoint.order_index)
        .all()
    )
    kp_count = len(kps)
    doc_count = (
        db.query(Document)
        .filter(Document.course_id == course.id)
        .count()
    )
    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "teacher_id": course.teacher_id,
        "created_at": course.created_at.isoformat() if course.created_at else "",
        "updated_at": course.updated_at.isoformat() if course.updated_at else "",
        "knowledge_point_count": kp_count,
        "document_count": doc_count,
        "knowledge_points": [
            {
                "id": kp.id,
                "neo4j_node_id": kp.neo4j_node_id,
                "name": kp.name,
                "description": kp.description,
                "order_index": kp.order_index,
                "level": kp.level if kp.level is not None else 2,
                "is_module": bool(kp.is_module),
            }
            for kp in kps
        ],
    }


# ---- 路由端点 ----

@router.post("/", response_model=CourseResponse, status_code=201)
def create_course(
    data: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建新课程（仅教师）。
    同时会在 Neo4j 中为该课程准备好知识图谱的存储空间。
    """
    _teacher_only(current_user)

    course = Course(
        title=data.title,
        description=data.description,
        teacher_id=current_user.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    return _build_course_response(course, db)


@router.get("/", response_model=List[CourseResponse])
def list_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取课程列表。
    - 教师：查看自己创建的课程
    - 学生：查看所有课程
    """
    if current_user.role == UserRole.TEACHER:
        courses = (
            db.query(Course)
            .filter(Course.teacher_id == current_user.id)
            .order_by(Course.created_at.asc())
            .all()
        )
    else:
        courses = (
            db.query(Course)
            .order_by(Course.created_at.asc())
            .all()
        )

    return [_build_course_response(c, db) for c in courses]


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取课程详情"""
    course = _get_course_or_404(course_id, db)
    return _build_course_response(course, db)


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(
    course_id: int,
    data: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新课程信息（仅该课程的教师）"""
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)

    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可编辑此课程")

    if data.title is not None:
        course.title = data.title
    if data.description is not None:
        course.description = data.description

    db.commit()
    db.refresh(course)

    return _build_course_response(course, db)


@router.delete("/{course_id}", status_code=204)
def delete_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除课程及其关联的所有数据（仅该课程的教师）"""
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)

    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可删除此课程")

    # 清除 Neo4j 中的图数据
    graph_ops.clear_course_graph(course_id)

    # 删除上传的文件
    documents = db.query(Document).filter(Document.course_id == course_id).all()
    for doc in documents:
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)

    # SQLite 中的级联删除由 cascade="all, delete-orphan" 处理
    db.delete(course)
    db.commit()


# ---- 文档上传与知识提取 ----

@router.post("/{course_id}/upload")
async def upload_document(
    course_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    为课程上传教学文档（PDF/DOCX）。
    上传后自动解析文档文本并存入数据库。
    """
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)

    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可上传文档")

    filename = Path((file.filename or "").replace("\\", "/")).name
    if not filename or any(ord(c) < 32 for c in filename):
        raise HTTPException(400, "无效文件名")
    # 验证文件类型
    if not DocumentParser.is_supported(filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式，仅支持: {', '.join(DocumentParser.SUPPORTED_EXTENSIONS)}",
        )

    # 检查文件大小
    content = await file.read(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    # 保存文件到磁盘
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(course_id))
    os.makedirs(upload_dir, exist_ok=True)

    file_path = str(Path(upload_dir).resolve() / (uuid.uuid4().hex + Path(filename).suffix.lower()))
    with open(file_path, "wb") as f:
        f.write(content)

    # 解析文档文本
    parser = DocumentParser()
    try:
        parsed_text = parser.parse(file_path)
        doc_status = DocumentStatus.PARSED
    except Exception as e:
        parsed_text = ""
        doc_status = DocumentStatus.FAILED

    # 创建文档记录
    document = Document(
        course_id=course_id,
        filename=filename,
        file_path=file_path,
        parsed_content=parsed_text,
        status=doc_status,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status.value,
        "parsed_length": len(parsed_text),
        "message": "文档上传并解析成功" if doc_status == DocumentStatus.PARSED
                   else "文档上传成功但解析失败",
    }



async def extract_knowledge(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    触发知识提取（仅教师）。
    从课程已上传的文档中提取知识点和关系，
    结果存入 Neo4j 图数据库和 SQLite 关系型数据库。
    """
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)

    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可执行知识提取")

    # 获取课程下所有已解析的文档
    documents = (
        db.query(Document)
        .filter(
            Document.course_id == course_id,
            Document.status.in_([DocumentStatus.PARSED, DocumentStatus.UPLOADED, DocumentStatus.EXTRACTED]),
        )
        .all()
    )

    if not documents:
        raise HTTPException(
            status_code=400,
            detail="课程没有可提取的文档，请先上传文档",
        )

    # 合并所有文档的文本
    all_text = "\n\n".join(
        doc.parsed_content for doc in documents if doc.parsed_content
    )

    if not all_text.strip():
        raise HTTPException(
            status_code=400,
            detail="文档内容为空，无法提取知识",
        )

    # 结束只读事务，抽取期间不占用数据库写锁。
    db.commit()
    # 调用 DeepSeek API 提取知识
    extractor = KnowledgeExtractor()
    try:
        extract_result = await extractor.extract(all_text)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"知识提取失败: {str(e)}",
        )

    modules = extract_result.get("modules", [])
    kps = extract_result.get("knowledge_points", [])
    relations = extract_result.get("relations", [])

    if not kps and not modules:
        return ExtractResult(
            knowledge_points_count=0, relations_count=0,
            knowledge_points=[], relations=[],
        )

    # 保留旧知识点 ID 及学习数据。相同名称更新，未匹配旧点留给教师审核。
    existing = {p.name: p for p in db.query(KnowledgePoint).filter_by(course_id=course_id).all()}
    sqlite_kps = {}
    for i, item in enumerate(kps):
        name = item["name"].strip()
        kp = existing.get(name)
        if kp is None:
            kp = KnowledgePoint(course_id=course_id, name=name, neo4j_node_id=uuid.uuid4().hex)
            db.add(kp)
        kp.description = item.get("description", "")
        kp.order_index = item.get("order_index", i)
        kp.level = item.get("level", 2)
        kp.is_module = item.get("is_module", False)
        db.flush()
        sqlite_kps[name] = kp
    for item in kps:
        parent = sqlite_kps.get(item.get("parent_name"))
        child = sqlite_kps[item["name"].strip()]
        if parent and parent.id == child.id:
            raise HTTPException(400, "抽取结果存在自包含关系")
        child.parent_id = parent.id if parent else None
    # 合并关系，保留教师已修正的关系，避免重抽覆盖人工数据。
    known = {(r.source_kp_id, r.target_kp_id, r.relation_type.value)
             for r in db.query(KnowledgeRelation).filter_by(course_id=course_id).all()}
    for item in relations:
        source, target = sqlite_kps.get(item["source"]), sqlite_kps.get(item["target"])
        kind = RelationType(item["relation_type"])
        if source and target and source.id != target.id:
            key = (source.id, target.id, kind.value)
            if key not in known:
                db.add(KnowledgeRelation(course_id=course_id, source_kp_id=source.id,
                                        target_kp_id=target.id, relation_type=kind))
                known.add(key)
    mark_pending(db, course_id)
    # 更新文档状态
    for doc in documents:
        doc.status = DocumentStatus.EXTRACTED
    db.commit()

    sync_course(db, course_id)
    return ExtractResult(
        knowledge_points_count=len(kps),
        relations_count=len(relations),
        knowledge_points=kps,
        relations=relations,
    )


# ---- 知识图谱查询 ----

@router.get("/{course_id}/graph", response_model=GraphResponse)
def get_course_graph(
    course_id: int,
    depth: int = Query(default=2, ge=0, le=2, description="显示深度: 0=仅模块, 1=模块+子模块, 2=全部"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取课程的知识图谱数据。

    depth 参数控制显示层级：
      - 0: 仅显示根模块（level=0），图谱最简洁
      - 1: 显示模块+子模块（level=0,1），隐藏叶子知识点
      - 2: 显示全部节点（默认）
    """
    _get_course_or_404(course_id, db)

    try:
        graph_data = graph_ops.get_course_graph(course_id)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"图数据库不可用: {str(e)}。请检查 Neo4j 连接配置。",
        )

    # 为每个节点附加 SQLite 主键，供前端点击节点跳转详情页使用
    kps = db.query(KnowledgePoint).filter(KnowledgePoint.course_id == course_id).all()
    kp_id_map = {kp.neo4j_node_id: kp.id for kp in kps}
    kp_name_map = {kp.name: kp.id for kp in kps}

    def _resolve_sqlite_id(node):
        # 优先按 neo4j_id 精确匹配；旧数据两库 id 不一致时按名称兜底
        return kp_id_map.get(node.get("id")) or kp_name_map.get(node.get("label"))

    # 构建 parent 映射，计算每个节点的根模块 id（供前端按根模块分组着色）
    parent_map = {n["id"]: n.get("parent_id") for n in graph_data["nodes"]}

    def _find_root(node_id):
        seen = set()
        cur = node_id
        while cur and cur in parent_map and parent_map.get(cur) and cur not in seen:
            seen.add(cur)
            cur = parent_map[cur]
        return cur

    for node in graph_data["nodes"]:
        node["sqlite_id"] = _resolve_sqlite_id(node)
        node["root_id"] = _find_root(node.get("id"))

    # 同样为树状结构的每个节点注入 SQLite 主键和根模块 id
    def _inject_tree(nodes):
        for n in nodes:
            n["sqlite_id"] = _resolve_sqlite_id(n)
            n["root_id"] = _find_root(n.get("id"))
            _inject_tree(n.get("children", []))
    _inject_tree(graph_data.get("tree", []))

    # 按深度过滤节点
    if depth < 2:
        filtered_nodes = [n for n in graph_data["nodes"] if n.get("level", 2) <= depth]
        filtered_ids = {n["id"] for n in filtered_nodes}
        filtered_edges = [
            e for e in graph_data["edges"]
            if e["source"] in filtered_ids and e["target"] in filtered_ids
        ]
        # 过滤树
        def filter_tree(nodes):
            result = []
            for n in nodes:
                if n.get("level", 2) <= depth:
                    result.append({**n, "children": filter_tree(n.get("children", []))})
                elif n.get("children"):
                    result.extend(filter_tree(n.get("children", [])))
            return result
        filtered_tree = filter_tree(graph_data.get("tree", []))
    else:
        filtered_nodes = graph_data["nodes"]
        filtered_edges = graph_data["edges"]
        filtered_tree = graph_data.get("tree", [])

    return GraphResponse(
        nodes=filtered_nodes,
        edges=filtered_edges,
        tree_edges=graph_data.get("tree_edges", []),
        cross_edges=graph_data.get("cross_edges", []),
        tree=filtered_tree,
    )


@router.delete("/{course_id}/graph")
def clear_course_graph(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清除课程的知识图谱（仅该课程的教师）"""
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)

    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可清除图谱")

    try:
        deleted_count = graph_ops.clear_course_graph(course_id)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"图数据库不可用: {str(e)}。请检查 Neo4j 连接配置。",
        )

    # 同步清除 SQLite 中的关联数据
    db.query(KnowledgeRelation).filter(
        KnowledgeRelation.course_id == course_id
    ).delete()
    db.query(KnowledgePoint).filter(
        KnowledgePoint.course_id == course_id
    ).delete()
    db.commit()

    return {"message": f"已清除 {deleted_count} 个知识点节点"}


# ---- 文档历史管理 ----

class DocumentResponse(BaseModel):
    id: int
    filename: str
    status: str
    parsed_length: int = 0
    created_at: str


@router.get("/{course_id}/documents", response_model=List[DocumentResponse])
def list_documents(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查询课程下所有上传文档的历史记录。
    包含文件名、处理状态（uploaded/parsed/extracted/failed）、
    解析后的文本长度和时间。
    """
    _get_course_or_404(course_id, db)

    docs = (
        db.query(Document)
        .filter(Document.course_id == course_id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return [
        DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            status=doc.status.value if doc.status else "unknown",
            parsed_length=len(doc.parsed_content) if doc.parsed_content else 0,
            created_at=doc.created_at.isoformat() if doc.created_at else "",
        )
        for doc in docs
    ]


@router.get("/{course_id}/documents/{doc_id}")
def get_document(
    course_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取单个文档详情，包含解析后的文本内容。
    可用于查看 AI 提取前的原始文本。
    """
    _get_course_or_404(course_id, db)

    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.course_id == course_id)
        .first()
    )

    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "id": doc.id,
        "filename": doc.filename,
        "status": doc.status.value if doc.status else "unknown",
        "parsed_content": doc.parsed_content,
        "parsed_length": len(doc.parsed_content) if doc.parsed_content else 0,
        "created_at": doc.created_at.isoformat() if doc.created_at else "",
    }


@router.delete("/{course_id}/documents/{doc_id}")
def delete_document(
    course_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除单个文档。
    仅课程创建者可操作。
    """
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)

    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可删除文档")

    doc = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.course_id == course_id)
        .first()
    )

    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 删除磁盘文件
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    db.delete(doc)
    db.commit()

    return {"message": f"文档 {doc.filename} 已删除"}


# ═══════════════════════════════════════════════════
#  知识点手动管理 (CRUD + AI 优化)
# ═══════════════════════════════════════════════════

class KPCreate(BaseModel):
    name: str
    description: str = ""
    parent_id: Optional[int] = None  # 父节点ID，null=根模块
    level: int = 2  # 0=模块, 1=子模块, 2=叶子
    is_module: bool = False


class KPUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[int] = None
    level: Optional[int] = None
    is_module: Optional[bool] = None


@router.post("/{course_id}/knowledge-points")
def create_knowledge_point(
    course_id: int,
    data: KPCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动添加知识点（仅教师）"""
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)
    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可操作")

    # 验证父节点
    if data.parent_id is not None:
        parent = db.query(KnowledgePoint).filter(
            KnowledgePoint.id == data.parent_id,
            KnowledgePoint.course_id == course_id
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父节点不存在")

    # 获取最大 order_index
    max_order = db.query(KnowledgePoint).filter(
        KnowledgePoint.course_id == course_id
    ).count()

    neo4j_id = f"kp_{course_id}_manual_{max_order}"
    kp = KnowledgePoint(
        neo4j_node_id=neo4j_id,
        course_id=course_id,
        name=data.name,
        description=data.description,
        order_index=max_order,
        level=data.level,
        is_module=data.is_module,
        parent_id=data.parent_id,
    )
    db.add(kp)
    db.commit()
    db.refresh(kp)

    # 同步写入 Neo4j
    try:
        graph_ops.create_knowledge_point(
            name=kp.name, description=kp.description,
            course_id=course_id, order_index=kp.order_index,
            neo4j_id=neo4j_id, level=kp.level,
            is_module=kp.is_module,
        )
        if kp.parent_id:
            parent_kp = db.query(KnowledgePoint).get(kp.parent_id)
            if parent_kp and parent_kp.neo4j_node_id:
                graph_ops.create_relation(neo4j_id, parent_kp.neo4j_node_id, "part_of")
    except Exception:
        pass  # Neo4j 不可用时跳过

    return {"id": kp.id, "name": kp.name, "neo4j_node_id": neo4j_id,
            "level": kp.level, "is_module": kp.is_module, "parent_id": kp.parent_id}


@router.put("/{course_id}/knowledge-points/{kp_id}")
def update_knowledge_point(
    course_id: int,
    kp_id: int,
    data: KPUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改知识点名称/描述/层级（仅教师）"""
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)
    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可操作")

    kp = db.query(KnowledgePoint).filter(
        KnowledgePoint.id == kp_id, KnowledgePoint.course_id == course_id
    ).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    updates = {}
    if data.name is not None:
        kp.name = data.name
        updates["name"] = data.name
    if data.description is not None:
        kp.description = data.description
        updates["description"] = data.description
    if data.level is not None:
        kp.level = data.level
        updates["level"] = data.level
    if data.is_module is not None:
        kp.is_module = data.is_module
        updates["is_module"] = data.is_module
    if data.parent_id is not None:
        kp.parent_id = data.parent_id
        updates["parent_id"] = data.parent_id

    db.commit()

    # 同步 Neo4j
    if kp.neo4j_node_id and updates:
        try:
            graph_ops.update_knowledge_point(
                kp.neo4j_node_id,
                name=updates.get("name"),
                description=updates.get("description"),
            )
        except Exception:
            pass

    return {"id": kp.id, "name": kp.name, "description": kp.description,
            "level": kp.level, "is_module": kp.is_module, "parent_id": kp.parent_id}


@router.delete("/{course_id}/knowledge-points/{kp_id}")
def delete_knowledge_point(
    course_id: int,
    kp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除知识点及其子节点（仅教师）"""
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)
    if current_user.id != course.teacher_id:
        raise HTTPException(status_code=403, detail="仅课程创建者可操作")

    kp = db.query(KnowledgePoint).filter(
        KnowledgePoint.id == kp_id, KnowledgePoint.course_id == course_id
    ).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 递归删除所有子节点
    def delete_children(parent_id: int):
        children = db.query(KnowledgePoint).filter(
            KnowledgePoint.parent_id == parent_id
        ).all()
        for child in children:
            delete_children(child.id)
            if child.neo4j_node_id:
                try:
                    graph_ops.delete_knowledge_point(child.neo4j_node_id)
                except Exception:
                    pass
            db.delete(child)

    delete_children(kp.id)

    # 删除 Neo4j 节点
    if kp.neo4j_node_id:
        try:
            graph_ops.delete_knowledge_point(kp.neo4j_node_id)
        except Exception:
            pass

    db.delete(kp)
    db.commit()

    return {"message": f"已删除知识点 {kp.name}"}


@router.post("/{course_id}/knowledge-points/{kp_id}/enhance")
async def enhance_description(
    course_id: int,
    kp_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI 优化知识点简介 — 用 DeepSeek 把描述改写得更清晰有条理。
    """
    course = _get_course_or_404(course_id, db)
    _teacher_only(current_user)

    kp = db.query(KnowledgePoint).filter(
        KnowledgePoint.id == kp_id, KnowledgePoint.course_id == course_id
    ).first()
    if not kp:
        raise HTTPException(status_code=404, detail="知识点不存在")

    import requests as req
    from app.core.config import get_settings
    s = get_settings()

    if not s.DEEPSEEK_API_KEY or s.DEEPSEEK_API_KEY in ("your-deepseek-api-key", ""):
        raise HTTPException(status_code=503, detail="DeepSeek API Key 未配置")

    prompt = f"""你是一个教育内容编辑。请把以下知识点的描述改写得更有条理、更清晰。
要求：结构清晰、分点说明（2-5点）、每点一句话、适合学生阅读、总字数不超过150字。

知识点名称：{kp.name}
原始描述：{kp.description or '（无）'}

请直接输出优化后的描述，不要加任何前缀。"""

    try:
        resp = req.post(
            f"{s.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {s.DEEPSEEK_API_KEY}"},
            json={"model": s.DEEPSEEK_MODEL, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.5, "max_tokens": 500},
            timeout=60, proxies={"http": None, "https": None},
        )
        enhanced = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 优化失败: {e}")

    # 保存
    old_desc = kp.description
    kp.description = enhanced
    db.commit()

    # 同步 Neo4j
    if kp.neo4j_node_id:
        try:
            graph_ops.update_knowledge_point(kp.neo4j_node_id, description=enhanced)
        except Exception:
            pass

    return {"id": kp.id, "name": kp.name, "old_description": old_desc, "enhanced_description": enhanced}
