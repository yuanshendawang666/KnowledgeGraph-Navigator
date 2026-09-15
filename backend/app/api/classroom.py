"""
班级系统 API (功能9)
--------------------
教师创建/管理班级、生成邀请码、查看成员与班级学习统计、布置学习任务；
学生凭邀请码加入班级、查看班级课程。
"""

import random
import string
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import (
    Classroom, ClassroomMember, ClassroomCourse, ClassroomTask,
    ClassroomTaskSubmission, ClassroomAnnouncement, ClassroomPost, ClassroomComment,
    User, UserRole, UserKnowledgeProgress, KnowledgePoint, KnowledgeStatus,
)

router = APIRouter(prefix="/api/classrooms", tags=["班级系统"])


class CRCreate(BaseModel):
    name: str
    description: str = ""


class CROut(BaseModel):
    id: int
    name: str
    description: str
    teacher_id: int
    invite_code: str
    member_count: int = 0
    created_at: str

    class Config:
        from_attributes = True


class CourseLink(BaseModel):
    course_id: int


class TaskCreate(BaseModel):
    course_id: Optional[int] = None
    title: str
    description: str = ""
    due_date: Optional[str] = None


def _gen_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


def _fmt(c: Classroom) -> CROut:
    cnt = len(c.members) if c.members else 0
    return CROut(
        id=c.id, name=c.name, description=c.description,
        teacher_id=c.teacher_id, invite_code=c.invite_code,
        member_count=cnt,
        created_at=c.created_at.isoformat() if c.created_at else "",
    )


def _require_teacher(u: User):
    if u.role != UserRole.TEACHER:
        raise HTTPException(403, "仅教师可执行此操作")


def _get_classroom_or_404(cr_id: int, db: Session) -> Classroom:
    c = db.query(Classroom).filter(Classroom.id == cr_id).first()
    if not c:
        raise HTTPException(404, "班级不存在")
    return c


# ============================================================
# 班级 CRUD
# ============================================================

@router.post("/", response_model=CROut)
def create(data: CRCreate, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    _require_teacher(u)
    c = Classroom(name=data.name, description=data.description,
                  teacher_id=u.id, invite_code=_gen_code())
    db.add(c); db.commit(); db.refresh(c)
    return _fmt(c)


@router.get("/", response_model=List[CROut])
def list_my(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    if u.role == UserRole.TEACHER:
        classrooms = db.query(Classroom).filter(Classroom.teacher_id == u.id).all()
    else:
        member_ids = [m.classroom_id for m in
                      db.query(ClassroomMember).filter(ClassroomMember.student_id == u.id).all()]
        classrooms = db.query(Classroom).filter(Classroom.id.in_(member_ids)).all() if member_ids else []
    return [_fmt(c) for c in classrooms]


@router.post("/join")
def join_by_code(invite_code: str, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """学生凭邀请码加入班级（邀请码唯一，无需班级 ID）。"""
    c = db.query(Classroom).filter(Classroom.invite_code == invite_code).first()
    if not c:
        raise HTTPException(404, "邀请码无效，请核对后重试")
    existing = db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == c.id, ClassroomMember.student_id == u.id).first()
    if existing:
        raise HTTPException(400, "已加入该班级")
    db.add(ClassroomMember(classroom_id=c.id, student_id=u.id)); db.commit()
    return {"message": f"已加入 {c.name}", "classroom_id": c.id}


@router.post("/{cr_id}/join")
def join(cr_id: int, invite_code: str, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    c = _get_classroom_or_404(cr_id, db)
    if c.invite_code != invite_code:
        raise HTTPException(400, "邀请码错误")
    existing = db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == cr_id, ClassroomMember.student_id == u.id).first()
    if existing:
        raise HTTPException(400, "已加入该班级")
    db.add(ClassroomMember(classroom_id=cr_id, student_id=u.id)); db.commit()
    return {"message": f"已加入 {c.name}"}


@router.get("/{cr_id}/members")
def members(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    ms = db.query(ClassroomMember).filter(ClassroomMember.classroom_id == cr_id).all()
    result = []
    for m in ms:
        student = db.query(User).get(m.student_id)
        result.append({
            "id": m.id, "student_id": m.student_id,
            "username": student.username if student else "",
            "joined_at": m.joined_at.isoformat() if m.joined_at else "",
        })
    return result


@router.delete("/{cr_id}")
def delete(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    _require_teacher(u)
    c = db.query(Classroom).filter(Classroom.id == cr_id, Classroom.teacher_id == u.id).first()
    if not c:
        raise HTTPException(404, "班级不存在或无权限")
    db.delete(c); db.commit()
    return {"message": "已删除"}


# ============================================================
# 班级课程关联
# ============================================================

@router.post("/{cr_id}/courses")
def add_course(cr_id: int, data: CourseLink, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可关联课程")
    exists = db.query(ClassroomCourse).filter(
        ClassroomCourse.classroom_id == cr_id, ClassroomCourse.course_id == data.course_id).first()
    if not exists:
        db.add(ClassroomCourse(classroom_id=cr_id, course_id=data.course_id)); db.commit()
    return {"message": "课程已关联"}


@router.get("/{cr_id}/courses")
def list_courses(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    links = db.query(ClassroomCourse).filter(ClassroomCourse.classroom_id == cr_id).all()
    result = []
    for link in links:
        course = link.course
        if course:
            result.append({"id": course.id, "title": course.title,
                           "description": course.description or ""})
    return result


@router.delete("/{cr_id}/courses/{course_id}")
def remove_course(cr_id: int, course_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """教师取消班级与课程的关联。"""
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可取消关联")
    link = db.query(ClassroomCourse).filter(
        ClassroomCourse.classroom_id == cr_id, ClassroomCourse.course_id == course_id).first()
    if not link:
        raise HTTPException(404, "该课程未关联")
    db.delete(link); db.commit()
    return {"message": "已取消关联"}


# ============================================================
# 班级学习统计
# ============================================================

@router.get("/{cr_id}/stats")
def classroom_stats(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """班级整体学习统计：各知识点掌握率、平均进度。"""
    c = _get_classroom_or_404(cr_id, db)
    members = db.query(ClassroomMember).filter(ClassroomMember.classroom_id == cr_id).all()
    student_ids = [m.student_id for m in members]

    if not student_ids:
        return {"classroom_id": cr_id, "member_count": 0, "average_progress": 0.0,
                "knowledge_points": []}

    course_ids = [l.course_id for l in
                  db.query(ClassroomCourse).filter(ClassroomCourse.classroom_id == cr_id).all()]
    if not course_ids:
        return {"classroom_id": cr_id, "member_count": len(student_ids),
                "average_progress": 0.0, "knowledge_points": []}

    kps = db.query(KnowledgePoint).filter(
        KnowledgePoint.course_id.in_(course_ids), KnowledgePoint.level == 2).all()
    kp_ids = [k.id for k in kps]

    progress = db.query(UserKnowledgeProgress).filter(
        UserKnowledgeProgress.knowledge_point_id.in_(kp_ids),
        UserKnowledgeProgress.user_id.in_(student_ids),
    ).all()

    # 每个知识点的掌握率
    kp_mastery = {}
    for p in progress:
        kp_mastery.setdefault(p.knowledge_point_id, []).append(p.mastery_level or 0.0)

    kp_stats = []
    total_rate = 0.0
    for kp in kps:
        levels = kp_mastery.get(kp.id, [])
        rate = sum(levels) / len(student_ids) if student_ids else 0.0
        mastered = sum(1 for lv in levels if lv >= 0.9)
        total_rate += rate
        kp_stats.append({
            "knowledge_point_id": kp.id,
            "name": kp.name,
            "mastery_rate": round(rate, 2),
            "mastered_count": mastered,
            "total_students": len(student_ids),
        })

    avg_progress = round(total_rate / len(kps), 2) if kps else 0.0

    return {
        "classroom_id": cr_id,
        "member_count": len(student_ids),
        "average_progress": avg_progress,
        "knowledge_points": kp_stats,
    }


# ============================================================
# 学习任务
# ============================================================

@router.post("/{cr_id}/tasks")
def create_task(cr_id: int, data: TaskCreate, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可布置任务")

    due = None
    if data.due_date:
        from datetime import datetime
        try:
            due = datetime.fromisoformat(data.due_date.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(400, "截止日期格式错误")

    t = ClassroomTask(classroom_id=cr_id, course_id=data.course_id,
                      title=data.title, description=data.description, due_date=due)
    db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id, "title": t.title, "due_date": t.due_date.isoformat() if t.due_date else None}


class TaskSubmit(BaseModel):
    note: str = ""


@router.get("/{cr_id}/tasks")
def list_tasks(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    tasks = db.query(ClassroomTask).filter(ClassroomTask.classroom_id == cr_id) \
        .order_by(ClassroomTask.created_at.desc()).all()

    member_count = db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == cr_id).count()

    result = []
    for t in tasks:
        item = {
            "id": t.id, "title": t.title, "description": t.description,
            "course_id": t.course_id,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "created_at": t.created_at.isoformat() if t.created_at else "",
        }
        submitted = db.query(ClassroomTaskSubmission).filter(
            ClassroomTaskSubmission.task_id == t.id).all()
        item["submitted_count"] = len(submitted)
        item["total_members"] = member_count
        my_sub = next((s for s in submitted if s.student_id == u.id), None)
        item["my_submitted"] = my_sub is not None
        if my_sub:
            item["my_note"] = my_sub.note
            item["my_submitted_at"] = my_sub.submitted_at.isoformat() if my_sub.submitted_at else ""
        result.append(item)
    return result


@router.post("/{cr_id}/tasks/{task_id}/submit")
def submit_task(cr_id: int, task_id: int, data: TaskSubmit, db: Session = Depends(get_db),
                u: User = Depends(get_current_user)):
    """学生提交/标记完成任务。"""
    task = db.query(ClassroomTask).filter(
        ClassroomTask.id == task_id, ClassroomTask.classroom_id == cr_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")
    # 学生需为班级成员
    member = db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == cr_id, ClassroomMember.student_id == u.id).first()
    if not member:
        raise HTTPException(403, "你不在该班级中")

    sub = db.query(ClassroomTaskSubmission).filter(
        ClassroomTaskSubmission.task_id == task_id,
        ClassroomTaskSubmission.student_id == u.id).first()
    if sub:
        sub.note = data.note
        from datetime import datetime, timezone
        sub.submitted_at = datetime.now(timezone.utc)
    else:
        sub = ClassroomTaskSubmission(task_id=task_id, student_id=u.id, note=data.note)
        db.add(sub)
    db.commit()
    return {"message": "已提交", "task_id": task_id, "note": data.note}


@router.get("/{cr_id}/tasks/{task_id}/submissions")
def task_submissions(cr_id: int, task_id: int, db: Session = Depends(get_db),
                     u: User = Depends(get_current_user)):
    """教师查看某任务的提交情况。"""
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可查看提交")

    task = db.query(ClassroomTask).filter(
        ClassroomTask.id == task_id, ClassroomTask.classroom_id == cr_id).first()
    if not task:
        raise HTTPException(404, "任务不存在")

    subs = db.query(ClassroomTaskSubmission).filter(
        ClassroomTaskSubmission.task_id == task_id).all()
    return [{
        "id": s.id, "student_id": s.student_id,
        "username": s.student.username if s.student else "",
        "note": s.note,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else "",
    } for s in subs]


# ============================================================
# 成员管理（移除 / 添加）
# ============================================================

class MemberAdd(BaseModel):
    username: str


@router.delete("/{cr_id}/members/{student_id}")
def remove_member(cr_id: int, student_id: int, db: Session = Depends(get_db),
                  u: User = Depends(get_current_user)):
    """教师移除班级成员。"""
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可移除成员")
    m = db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == cr_id,
        ClassroomMember.student_id == student_id).first()
    if not m:
        raise HTTPException(404, "该成员不在班级中")
    db.delete(m); db.commit()
    return {"message": "已移除成员"}


@router.post("/{cr_id}/members")
def add_member(cr_id: int, data: MemberAdd, db: Session = Depends(get_db),
               u: User = Depends(get_current_user)):
    """教师按用户名直接添加学生（无需邀请码）。"""
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可添加成员")
    student = db.query(User).filter(User.username == data.username).first()
    if not student:
        raise HTTPException(404, "用户不存在")
    if student.role != UserRole.STUDENT:
        raise HTTPException(400, "只能添加学生账号")
    existing = db.query(ClassroomMember).filter(
        ClassroomMember.classroom_id == cr_id, ClassroomMember.student_id == student.id).first()
    if existing:
        raise HTTPException(400, "该学生已在班级中")
    db.add(ClassroomMember(classroom_id=cr_id, student_id=student.id)); db.commit()
    return {"message": f"已添加 {student.username}", "student_id": student.id}


# ============================================================
# 学习排名
# ============================================================

@router.get("/{cr_id}/ranking")
def classroom_ranking(cr_id: int, db: Session = Depends(get_db),
                      u: User = Depends(get_current_user)):
    """班级学习排名：按平均掌握率排序。"""
    _get_classroom_or_404(cr_id, db)
    members = db.query(ClassroomMember).filter(ClassroomMember.classroom_id == cr_id).all()
    student_ids = [m.student_id for m in members]
    if not student_ids:
        return {"classroom_id": cr_id, "ranking": []}

    course_ids = [l.course_id for l in db.query(ClassroomCourse).filter(
        ClassroomCourse.classroom_id == cr_id).all()]
    kp_ids = []
    if course_ids:
        kp_ids = [k.id for k in db.query(KnowledgePoint).filter(
            KnowledgePoint.course_id.in_(course_ids), KnowledgePoint.level == 2).all()]

    ranking = []
    for sid in student_ids:
        student = db.query(User).get(sid)
        if not student:
            continue
        avg = 0.0
        mastered = 0
        if kp_ids:
            progress = db.query(UserKnowledgeProgress).filter(
                UserKnowledgeProgress.user_id == sid,
                UserKnowledgeProgress.knowledge_point_id.in_(kp_ids)).all()
            levels = [p.mastery_level or 0.0 for p in progress]
            avg = round(sum(levels) / len(kp_ids), 3) if kp_ids else 0.0
            mastered = sum(1 for lv in levels if lv >= 0.9)
        ranking.append({
            "student_id": sid,
            "username": student.username,
            "average_mastery": avg,
            "mastered_count": mastered,
            "total_points": len(kp_ids),
        })

    ranking.sort(key=lambda x: x["average_mastery"], reverse=True)
    for i, r in enumerate(ranking, 1):
        r["rank"] = i
    return {"classroom_id": cr_id, "ranking": ranking}


# ============================================================
# 班级公告
# ============================================================

class AnnouncementCreate(BaseModel):
    title: str
    content: str = ""


@router.post("/{cr_id}/announcements")
def create_announcement(cr_id: int, data: AnnouncementCreate, db: Session = Depends(get_db),
                        u: User = Depends(get_current_user)):
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可发公告")
    a = ClassroomAnnouncement(classroom_id=cr_id, author_id=u.id,
                              title=data.title, content=data.content)
    db.add(a); db.commit(); db.refresh(a)
    return {"id": a.id, "title": a.title, "created_at": a.created_at.isoformat() if a.created_at else ""}


@router.get("/{cr_id}/announcements")
def list_announcements(cr_id: int, db: Session = Depends(get_db),
                       u: User = Depends(get_current_user)):
    anns = db.query(ClassroomAnnouncement).filter(
        ClassroomAnnouncement.classroom_id == cr_id) \
        .order_by(ClassroomAnnouncement.created_at.desc()).all()
    return [{
        "id": a.id, "title": a.title, "content": a.content,
        "author": a.author.username if a.author else "",
        "created_at": a.created_at.isoformat() if a.created_at else "",
    } for a in anns]


@router.delete("/{cr_id}/announcements/{ann_id}")
def delete_announcement(cr_id: int, ann_id: int, db: Session = Depends(get_db),
                        u: User = Depends(get_current_user)):
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可删除公告")
    a = db.query(ClassroomAnnouncement).filter(
        ClassroomAnnouncement.id == ann_id, ClassroomAnnouncement.classroom_id == cr_id).first()
    if not a:
        raise HTTPException(404, "公告不存在")
    db.delete(a); db.commit()
    return {"message": "已删除公告"}


# ============================================================
# 成绩导出 CSV
# ============================================================

@router.get("/{cr_id}/export")
def export_csv(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """导出班级成绩明细为 CSV（教师）。"""
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可导出")

    ranking = classroom_ranking(cr_id, db, u)["ranking"]
    if not ranking:
        return {"filename": f"{c.name}_成绩.csv", "csv": "暂无数据"}

    # 构建表头（学生 + 各知识点掌握率 + 平均）
    course_ids = [l.course_id for l in db.query(ClassroomCourse).filter(
        ClassroomCourse.classroom_id == cr_id).all()]
    kps = db.query(KnowledgePoint).filter(
        KnowledgePoint.course_id.in_(course_ids), KnowledgePoint.level == 2) \
        .order_by(KnowledgePoint.order_index).all() if course_ids else []

    header = ["排名", "学生"] + [k.name for k in kps] + ["平均掌握率"]
    rows = [header]
    for r in ranking:
        # 逐知识点掌握率
        per_kp = []
        for k in kps:
            p = db.query(UserKnowledgeProgress).filter(
                UserKnowledgeProgress.user_id == r["student_id"],
                UserKnowledgeProgress.knowledge_point_id == k.id).first()
            per_kp.append(f"{p.mastery_level:.2f}" if p else "0.00")
        rows.append([str(r["rank"]), r["username"]] + per_kp + [f"{r['average_mastery']:.2f}"])

    def esc(v):
        return '"' + str(v).replace('"', '""') + '"'
    csv = "﻿" + "\n".join(",".join(esc(v) for v in row) for row in rows)
    return {"filename": f"{c.name}_成绩.csv", "csv": csv}


# ============================================================
# AI 学情报告
# ============================================================

@router.post("/{cr_id}/ai-report")
async def ai_report(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """用 DeepSeek 生成班级学情诊断报告（教师）。"""
    c = _get_classroom_or_404(cr_id, db)
    _require_teacher(u)
    if c.teacher_id != u.id:
        raise HTTPException(403, "仅班级创建者可生成报告")

    stats = classroom_stats(cr_id, db, u)
    kps = stats.get("knowledge_points", [])
    if not kps:
        raise HTTPException(400, "班级暂无知识点数据，请先关联课程")

    from app.core.config import get_settings
    settings = get_settings()
    if not settings.DEEPSEEK_API_KEY or settings.DEEPSEEK_API_KEY in ("your-deepseek-api-key", ""):
        raise HTTPException(503, "DeepSeek API Key 未配置")

    # 构建统计摘要文本
    lines = []
    for kp in kps:
        weak = "⚠️ 薄弱" if kp["mastery_rate"] < 0.6 else ("一般" if kp["mastery_rate"] < 0.8 else "良好")
        lines.append(f"- {kp['name']}：掌握率 {round(kp['mastery_rate']*100)}%（{weak}）")
    summary = "\n".join(lines)

    prompt = f"""你是教学分析专家。请根据以下班级学习统计数据，生成一份简明扼要的学情诊断报告。

班级：{c.name}
平均进度：{round(stats['average_progress']*100)}%
成员数：{stats['member_count']}人

各知识点掌握情况：
{summary}

请输出（用 Markdown，分三部分）：
1. 整体评价（2-3句）
2. 薄弱知识点分析（指出最需要补的 2-3 个点）
3. 教学建议（3-4条可操作建议）"""

    import requests
    try:
        resp = requests.post(
            f"{settings.DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": settings.DEEPSEEK_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.5, "max_tokens": 1500},
            timeout=60, proxies={"http": None, "https": None},
        )
        report = resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        raise HTTPException(500, f"AI 报告生成失败: {e}")

    return {"report": report}


# ============================================================
# 班级讨论区
# ============================================================

class PostCreate(BaseModel):
    title: str
    content: str = ""


class CommentCreate(BaseModel):
    content: str


@router.post("/{cr_id}/posts")
def create_post(cr_id: int, data: PostCreate, db: Session = Depends(get_db),
                u: User = Depends(get_current_user)):
    _get_classroom_or_404(cr_id, db)
    p = ClassroomPost(classroom_id=cr_id, author_id=u.id, title=data.title, content=data.content)
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id, "title": p.title}


@router.get("/{cr_id}/posts")
def list_posts(cr_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    posts = db.query(ClassroomPost).filter(ClassroomPost.classroom_id == cr_id) \
        .order_by(ClassroomPost.created_at.desc()).all()
    return [{
        "id": p.id, "title": p.title, "content": p.content,
        "author": p.author.username if p.author else "",
        "comment_count": len(p.comments),
        "created_at": p.created_at.isoformat() if p.created_at else "",
        "comments": [{
            "id": cm.id, "content": cm.content,
            "author": cm.author.username if cm.author else "",
            "created_at": cm.created_at.isoformat() if cm.created_at else "",
        } for cm in p.comments],
    } for p in posts]


@router.post("/{cr_id}/posts/{post_id}/comments")
def create_comment(cr_id: int, post_id: int, data: CommentCreate, db: Session = Depends(get_db),
                   u: User = Depends(get_current_user)):
    post = db.query(ClassroomPost).filter(
        ClassroomPost.id == post_id, ClassroomPost.classroom_id == cr_id).first()
    if not post:
        raise HTTPException(404, "帖子不存在")
    cm = ClassroomComment(post_id=post_id, author_id=u.id, content=data.content)
    db.add(cm); db.commit()
    return {"message": "已回复", "id": cm.id}


@router.delete("/{cr_id}/posts/{post_id}")
def delete_post(cr_id: int, post_id: int, db: Session = Depends(get_db),
                u: User = Depends(get_current_user)):
    c = _get_classroom_or_404(cr_id, db)
    post = db.query(ClassroomPost).filter(
        ClassroomPost.id == post_id, ClassroomPost.classroom_id == cr_id).first()
    if not post:
        raise HTTPException(404, "帖子不存在")
    if post.author_id != u.id and c.teacher_id != u.id:
        raise HTTPException(403, "仅作者或教师可删除")
    db.delete(post); db.commit()
    return {"message": "已删除帖子"}
