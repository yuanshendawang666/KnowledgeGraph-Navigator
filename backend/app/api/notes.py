"""
学习笔记 API (功能6)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import Note, User

router = APIRouter(prefix="/api/notes", tags=["学习笔记"])

class NoteCreate(BaseModel):
    knowledge_point_id: int
    course_id: int
    title: str
    content: str = ""
    tags: str = ""
    is_public: bool = False

class NoteUpdate(BaseModel):
    title: Optional[str] = None; content: Optional[str] = None; tags: Optional[str] = None; is_public: Optional[bool] = None

class NoteOut(BaseModel):
    id: int; user_id: int; username: str = ""; knowledge_point_id: int; course_id: int
    title: str; content: str; tags: str; is_public: bool; created_at: str; updated_at: str
    class Config: from_attributes = True

@router.post("/", response_model=NoteOut)
def create_note(data: NoteCreate, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    n = Note(user_id=u.id, **data.dict())
    db.add(n); db.commit(); db.refresh(n)
    return _format(n, u)

@router.get("/", response_model=List[NoteOut])
def list_notes(kp_id: Optional[int] = None, course_id: Optional[int] = None, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    q = db.query(Note).filter((Note.user_id == u.id) | (Note.is_public == True))
    if kp_id: q = q.filter(Note.knowledge_point_id == kp_id)
    if course_id: q = q.filter(Note.course_id == course_id)
    return [_format(n, u) for n in q.order_by(Note.updated_at.desc()).all()]

@router.put("/{note_id}", response_model=NoteOut)
def update_note(note_id: int, data: NoteUpdate, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    n = db.query(Note).filter(Note.id == note_id, Note.user_id == u.id).first()
    if not n: raise HTTPException(404, "笔记不存在")
    for k, v in data.dict(exclude_unset=True).items(): setattr(n, k, v)
    db.commit(); db.refresh(n)
    return _format(n, u)

@router.delete("/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    n = db.query(Note).filter(Note.id == note_id, Note.user_id == u.id).first()
    if not n: raise HTTPException(404, "笔记不存在")
    db.delete(n); db.commit()
    return {"message": "已删除"}

def _format(n: Note, u: User) -> NoteOut:
    return NoteOut(id=n.id, user_id=n.user_id, username=n.user.username if n.user else "", knowledge_point_id=n.knowledge_point_id, course_id=n.course_id, title=n.title, content=n.content, tags=n.tags, is_public=n.is_public, created_at=n.created_at.isoformat() if n.created_at else "", updated_at=n.updated_at.isoformat() if n.updated_at else "")
