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
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Form, status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import (
    User, Course, KnowledgePoint, KnowledgeRelation, Document,
    DocumentStatus, UserRole, RelationType,
)
from app.api.auth import get_current_user
from app.services.parser import DocumentParser
from app.services.extractor import KnowledgeExtractor
from app.services.graph_ops import GraphOperations

settings = get_settings()
router = APIRouter(prefix="/api/courses", tags=["课程与图谱管理"])

graph_ops = GraphOperations()


# ---- 请求/响应模型 ----

class CourseCreate(BaseModel):
    title: str
    description: str = ""


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class CourseResponse(BaseModel):
    id: int
    title: str
    description: str
    teacher_id: int
    created_at: str
    updated_at: str
    knowledge_point_count: int = 0
    document_count: int = 0

    class Config:
        from_attributes = True


class GraphResponse(BaseModel):
    nodes: list
    edges: list


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
    kp_count = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.course_id == course.id)
        .count()
    )
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
            .order_by(Course.updated_at.desc())
            .all()
        )
    else:
        courses = (
            db.query(Course)
            .order_by(Course.updated_at.desc())
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

    # 验证文件类型
    if not DocumentParser.is_supported(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式，仅支持: {', '.join(DocumentParser.SUPPORTED_EXTENSIONS)}",
        )

    # 检查文件大小
    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制 ({settings.MAX_UPLOAD_SIZE_MB}MB)",
        )

    # 保存文件到磁盘
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(course_id))
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
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
        filename=file.filename,
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


@router.post("/{course_id}/extract", response_model=ExtractResult)
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
            Document.status.in_([DocumentStatus.PARSED, DocumentStatus.UPLOADED]),
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

    # 调用 DeepSeek API 提取知识
    extractor = KnowledgeExtractor()
    try:
        extract_result = await extractor.extract(all_text)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"知识提取失败: {str(e)}",
        )

    kps = extract_result.get("knowledge_points", [])
    relations = extract_result.get("relations", [])

    if not kps:
        return ExtractResult(
            knowledge_points_count=0,
            relations_count=0,
            knowledge_points=[],
            relations=[],
        )

    # ---- 先清除旧的图数据和关系型数据 ----
    # 清除 Neo4j 中的旧图
    graph_ops.clear_course_graph(course_id)

    # 清除 SQLite 中的旧知识点和关系记录
    db.query(KnowledgeRelation).filter(
        KnowledgeRelation.course_id == course_id
    ).delete()
    db.query(KnowledgePoint).filter(
        KnowledgePoint.course_id == course_id
    ).delete()
    db.commit()

    # ---- 写入 Neo4j ----
    graph_ops.bulk_create_knowledge_points(kps, course_id)
    graph_ops.bulk_create_relations(relations, course_id)

    # ---- 写入 SQLite ----
    # 创建知识点记录
    sqlite_kps = {}
    for i, kp_data in enumerate(kps):
        neo4j_id = f"kp_{course_id}_{kp_data.get('order_index', i)}"
        kp = KnowledgePoint(
            neo4j_node_id=neo4j_id,
            course_id=course_id,
            name=kp_data["name"],
            description=kp_data.get("description", ""),
            order_index=kp_data.get("order_index", i),
        )
        db.add(kp)
        db.flush()  # 获取自增 ID
        sqlite_kps[kp_data["name"]] = kp

    # 创建关系记录
    for rel_data in relations:
        source_kp = sqlite_kps.get(rel_data["source"])
        target_kp = sqlite_kps.get(rel_data["target"])
        if source_kp and target_kp:
            relation = KnowledgeRelation(
                course_id=course_id,
                source_kp_id=source_kp.id,
                target_kp_id=target_kp.id,
                relation_type=RelationType(rel_data["relation_type"]),
            )
            db.add(relation)

    # 更新文档状态
    for doc in documents:
        doc.status = DocumentStatus.EXTRACTED

    db.commit()

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取课程的知识图谱数据（节点 + 边），
    适用于前端 AntV G6 可视化渲染。
    """
    _get_course_or_404(course_id, db)

    graph_data = graph_ops.get_course_graph(course_id)
    return GraphResponse(
        nodes=graph_data["nodes"],
        edges=graph_data["edges"],
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

    deleted_count = graph_ops.clear_course_graph(course_id)

    # 同步清除 SQLite 中的关联数据
    db.query(KnowledgeRelation).filter(
        KnowledgeRelation.course_id == course_id
    ).delete()
    db.query(KnowledgePoint).filter(
        KnowledgePoint.course_id == course_id
    ).delete()
    db.commit()

    return {"message": f"已清除 {deleted_count} 个知识点节点"}
