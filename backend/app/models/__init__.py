"""
数据模型模块
------------
使用 SQLAlchemy ORM 定义关系型数据表结构。

表结构概览：
- User: 用户（教师/学生）
- Course: 课程
- KnowledgePoint: 知识点（关系型备份，主存储为 Neo4j）
- KnowledgeRelation: 知识点关系（关系型备份）
- Document: 上传的文档
- UserKnowledgeProgress: 用户学习进度
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Enum,
    ForeignKey, Float, Boolean,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============================================================
# 枚举类型
# ============================================================

class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"


class KnowledgeStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    MASTERED = "mastered"


class RelationType(str, enum.Enum):
    PREREQUISITE = "prerequisite"   # A 是 B 的先修知识点
    RELATED_TO = "related_to"       # A 与 B 相关
    PART_OF = "part_of"             # A 是 B 的组成部分


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSED = "parsed"
    EXTRACTED = "extracted"
    FAILED = "failed"


# ============================================================
# 数据表模型
# ============================================================

class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系
    courses_teaching = relationship("Course", back_populates="teacher")
    progress_records = relationship("UserKnowledgeProgress", back_populates="user")


class Course(Base):
    """课程表"""
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # 关系
    teacher = relationship("User", back_populates="courses_teaching")
    knowledge_points = relationship("KnowledgePoint", back_populates="course",
                                    cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="course",
                             cascade="all, delete-orphan")


class KnowledgePoint(Base):
    """
    知识点表（关系型备份）
    主存储为 Neo4j 图中的 KnowledgePoint 节点。
    此表用于快速查询和与关系型数据的关联。
    """
    __tablename__ = "knowledge_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    neo4j_node_id = Column(String(100), unique=True, nullable=True,
                           comment="对应 Neo4j 中的节点 ID")
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系
    course = relationship("Course", back_populates="knowledge_points")
    progress_records = relationship("UserKnowledgeProgress",
                                    back_populates="knowledge_point")


class KnowledgeRelation(Base):
    """知识点关系表（关系型备份）"""
    __tablename__ = "knowledge_relations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    source_kp_id = Column(Integer, ForeignKey("knowledge_points.id"),
                          nullable=False)
    target_kp_id = Column(Integer, ForeignKey("knowledge_points.id"),
                          nullable=False)
    relation_type = Column(Enum(RelationType), nullable=False)

    # 关系
    course = relationship("Course")
    source_kp = relationship("KnowledgePoint", foreign_keys=[source_kp_id])
    target_kp = relationship("KnowledgePoint", foreign_keys=[target_kp_id])


class Document(Base):
    """上传的文档表"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    parsed_content = Column(Text, default="")
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系
    course = relationship("Course", back_populates="documents")


class UserKnowledgeProgress(Base):
    """用户学习进度表"""
    __tablename__ = "user_knowledge_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"),
                                nullable=False)
    status = Column(Enum(KnowledgeStatus), default=KnowledgeStatus.NOT_STARTED)
    mastery_level = Column(Float, default=0.0,
                           comment="掌握程度 0.0~1.0")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # 关系
    user = relationship("User", back_populates="progress_records")
    knowledge_point = relationship("KnowledgePoint",
                                   back_populates="progress_records")
