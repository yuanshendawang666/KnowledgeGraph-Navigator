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


class QuestionType(str, enum.Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"


class QuestionDifficulty(str, enum.Enum):
    BASIC = "basic"
    ADVANCED = "advanced"


class QuizMode(str, enum.Enum):
    ADAPTIVE = "adaptive"
    KNOWLEDGE_POINT = "knowledge_point"
    WRONG_BOOK = "wrong_book"


class QuizSessionStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class QuestionSource(str, enum.Enum):
    AI_GENERATED = "ai_generated"
    TEACHER_EDITED = "teacher_edited"


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
    # ── 用户画像字段（功能1：个性化推荐） ──
    major = Column(String(100), default="", comment="专业（计算机科学/数学/物理 等）")
    grade = Column(String(50), default="", comment="年级")
    learning_goal = Column(String(200), default="", comment="学习目标（应试/兴趣/考研 等）")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系
    courses_teaching = relationship("Course", back_populates="teacher")
    progress_records = relationship("UserKnowledgeProgress", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user",
                                 cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")


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
    知识点表 — 树状结构（模块 → 子模块 → 知识点）

    层级说明：
      level=0  知识模块 (module)   — 如 "Python基础"
      level=1  子模块   (sub_module) — 如 "变量与数据类型"
      level=2  叶子知识点 (leaf)    — 如 "整数类型int"

    主存储为 Neo4j 图中的 KnowledgePoint 节点，
    Module 节点有额外的 :Module 标签用于区分。
    """
    __tablename__ = "knowledge_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    neo4j_node_id = Column(String(100), unique=True, nullable=True,
                           comment="对应 Neo4j 中的节点 ID")
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    order_index = Column(Integer, default=0)

    # ── 树状结构字段 ──
    parent_id = Column(Integer, ForeignKey("knowledge_points.id"), nullable=True,
                       comment="父节点 ID，NULL 表示根模块")
    level = Column(Integer, default=2,
                   comment="层级: 0=根模块, 1=子模块, 2=叶子知识点")
    is_module = Column(Boolean, default=False,
                       comment="是否为模块节点（可包含子节点）")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # 关系
    course = relationship("Course", back_populates="knowledge_points")
    progress_records = relationship("UserKnowledgeProgress",
                                    back_populates="knowledge_point")
    # 自引用：父节点和子节点
    parent = relationship("KnowledgePoint", remote_side=[id], backref="children")


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


class Question(Base):
    """练习题库"""
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"),
                                nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    difficulty = Column(Enum(QuestionDifficulty), default=QuestionDifficulty.BASIC)
    content = Column(Text, nullable=False)
    options = Column(Text, default="[]", comment="JSON 选项列表")
    correct_answer = Column(String(100), nullable=False)
    explanation = Column(Text, default="")
    source = Column(Enum(QuestionSource), default=QuestionSource.AI_GENERATED)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    knowledge_point = relationship("KnowledgePoint")
    course = relationship("Course")


class QuizSession(Base):
    """练习会话"""
    __tablename__ = "quiz_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    mode = Column(Enum(QuizMode), nullable=False)
    difficulty = Column(Enum(QuestionDifficulty), default=QuestionDifficulty.BASIC)
    target_kp_ids = Column(Text, default="[]", comment="JSON 知识点 ID 列表")
    total_count = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    score = Column(Float, default=0.0, comment="总分 0.0~1.0")
    status = Column(Enum(QuizSessionStatus), default=QuizSessionStatus.IN_PROGRESS)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)

    user = relationship("User")
    course = relationship("Course")
    answers = relationship("UserAnswer", back_populates="session",
                           cascade="all, delete-orphan")
    session_questions = relationship("QuizSessionQuestion",
                                     back_populates="session",
                                     cascade="all, delete-orphan")


class QuizSessionQuestion(Base):
    """练习会话与题目的关联（保持出题顺序）"""
    __tablename__ = "quiz_session_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    order_index = Column(Integer, default=0)

    session = relationship("QuizSession", back_populates="session_questions")
    question = relationship("Question")


class UserAnswer(Base):
    """用户答题记录"""
    __tablename__ = "user_answers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("quiz_sessions.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user_answer = Column(String(500), default="")
    is_correct = Column(Boolean, default=False)
    score = Column(Float, default=0.0)
    answered_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("QuizSession", back_populates="answers")
    question = relationship("Question")


class WrongQuestion(Base):
    """错题本"""
    __tablename__ = "wrong_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"),
                                nullable=False)
    wrong_count = Column(Integer, default=1)
    last_wrong_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    mastered = Column(Boolean, default=False)

    question = relationship("Question")
    knowledge_point = relationship("KnowledgePoint")


# ============================================================
# 功能1：用户学习行为（推荐增强用）
# ============================================================

class LearningBehavior(Base):
    """用户学习行为记录表（事件日志，用于推荐增强）"""
    __tablename__ = "learning_behaviors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"),
                               nullable=True, comment="可空，为空表示课程级行为")
    action = Column(String(50), nullable=False, default="study",
                    comment="行为类型: study/view/quiz")
    duration_seconds = Column(Integer, default=0, comment="学习时长（秒）")
    score = Column(Float, default=0.0, comment="答题得分 0.0~1.0")
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
    course = relationship("Course")
    knowledge_point = relationship("KnowledgePoint")


# ============================================================
# 功能3：智能对话历史
# ============================================================

class ChatSession(Base):
    """问答会话"""
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True,
                       comment="关联课程（可空，全局问答）")
    title = Column(String(200), default="新对话")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="chat_sessions")
    course = relationship("Course")
    messages = relationship("ChatMessage", back_populates="session",
                            cascade="all, delete-orphan", order_by="ChatMessage.id")


class ChatMessage(Base):
    """问答消息"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False, comment="user / assistant")
    content = Column(Text, default="")
    references_json = Column(Text, default="[]", comment="RAG 引用来源 JSON")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ChatSession", back_populates="messages")


# ============================================================
# 功能6：学习笔记
# ============================================================

class Note(Base):
    """学习笔记"""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    knowledge_point_id = Column(Integer, ForeignKey("knowledge_points.id"),
                                nullable=False, comment="关联知识点")
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    tags = Column(String(500), default="", comment="逗号分隔标签")
    is_public = Column(Boolean, default=False, comment="是否公开")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="notes")
    course = relationship("Course")
    knowledge_point = relationship("KnowledgePoint")
    knowledge_point = relationship("KnowledgePoint")


# ============================================================
# 功能9：班级系统
# ============================================================

class Classroom(Base):
    """班级"""
    __tablename__ = "classrooms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    description = Column(Text, default="")
    invite_code = Column(String(20), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    teacher = relationship("User")
    members = relationship("ClassroomMember", back_populates="classroom",
                           cascade="all, delete-orphan")
    courses = relationship("ClassroomCourse", back_populates="classroom",
                           cascade="all, delete-orphan")
    tasks = relationship("ClassroomTask", back_populates="classroom",
                         cascade="all, delete-orphan")
    announcements = relationship("ClassroomAnnouncement", back_populates="classroom",
                                 cascade="all, delete-orphan")
    posts = relationship("ClassroomPost", back_populates="classroom",
                         cascade="all, delete-orphan")


class ClassroomMember(Base):
    """班级成员（学生）"""
    __tablename__ = "classroom_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    classroom = relationship("Classroom", back_populates="members")
    student = relationship("User")


class ClassroomCourse(Base):
    """班级关联课程"""
    __tablename__ = "classroom_courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)

    classroom = relationship("Classroom", back_populates="courses")
    course = relationship("Course")


class ClassroomTask(Base):
    """班级学习任务"""
    __tablename__ = "classroom_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    due_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    classroom = relationship("Classroom", back_populates="tasks")
    course = relationship("Course")
    submissions = relationship("ClassroomTaskSubmission", back_populates="task",
                               cascade="all, delete-orphan")


class ClassroomTaskSubmission(Base):
    """班级任务提交记录"""
    __tablename__ = "classroom_task_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("classroom_tasks.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="completed", comment="completed 已提交")
    note = Column(Text, default="", comment="学生备注")
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    task = relationship("ClassroomTask", back_populates="submissions")
    student = relationship("User")


class ClassroomAnnouncement(Base):
    """班级公告"""
    __tablename__ = "classroom_announcements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    classroom = relationship("Classroom", back_populates="announcements")
    author = relationship("User")


class ClassroomPost(Base):
    """班级讨论帖"""
    __tablename__ = "classroom_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    classroom = relationship("Classroom", back_populates="posts")
    author = relationship("User")
    comments = relationship("ClassroomComment", back_populates="post",
                            cascade="all, delete-orphan", order_by="ClassroomComment.id")


class ClassroomComment(Base):
    """班级讨论回复"""
    __tablename__ = "classroom_comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("classroom_posts.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    post = relationship("ClassroomPost", back_populates="comments")
    author = relationship("User")
