"""
智能对话历史 API (功能3)
"""
import os
import re
import textwrap
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models import ChatSession, ChatMessage, User

router = APIRouter(prefix="/api/chat", tags=["对话历史"])

class SessionOut(BaseModel):
    id: int; title: str; course_id: Optional[int]; created_at: str; updated_at: str; msg_count: int = 0
    class Config: from_attributes = True

class MessageOut(BaseModel):
    id: int; role: str; content: str; references_json: str; created_at: str
    class Config: from_attributes = True

@router.post("/sessions", response_model=SessionOut)
def create_session(course_id: Optional[int] = None, title: str = "新对话", db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    s = ChatSession(user_id=u.id, course_id=course_id, title=title)
    db.add(s); db.commit(); db.refresh(s)
    return SessionOut(id=s.id, title=s.title, course_id=s.course_id, created_at=s.created_at.isoformat(), updated_at=s.updated_at.isoformat(), msg_count=0)

@router.get("/sessions", response_model=List[SessionOut])
def list_sessions(course_id: Optional[int] = None, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    q = db.query(ChatSession).filter(ChatSession.user_id == u.id)
    if course_id: q = q.filter(ChatSession.course_id == course_id)
    sessions = q.order_by(ChatSession.updated_at.desc()).all()
    return [SessionOut(id=s.id, title=s.title, course_id=s.course_id, created_at=s.created_at.isoformat(), updated_at=s.updated_at.isoformat(), msg_count=len(s.messages)) for s in sessions]

@router.get("/sessions/{session_id}/messages", response_model=List[MessageOut])
def get_messages(session_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == u.id).first()
    if not s: raise HTTPException(404, "会话不存在")
    return [MessageOut(id=m.id, role=m.role, content=m.content, references_json=m.references_json, created_at=m.created_at.isoformat()) for m in s.messages]

@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == u.id).first()
    if not s: raise HTTPException(404, "会话不存在")
    db.delete(s); db.commit()
    return {"message": "已删除"}

@router.put("/sessions/{session_id}")
def rename_session(session_id: int, title: str, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    s = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == u.id).first()
    if not s: raise HTTPException(404, "会话不存在")
    s.title = title; db.commit()
    return {"message": "已重命名"}


# ============================================================
# 对话导出（Markdown / PDF）
# ============================================================

def _get_owned_session(session_id: int, db: Session, u: User) -> ChatSession:
    s = db.query(ChatSession).filter(
        ChatSession.id == session_id, ChatSession.user_id == u.id).first()
    if not s:
        raise HTTPException(404, "会话不存在")
    return s


def _build_markdown(s: ChatSession) -> str:
    """将会话拼接为 Markdown 文本。"""
    lines = [f"# {s.title}", ""]
    created = s.created_at.isoformat() if s.created_at else ""
    lines.append(f"创建时间：{created}")
    lines.append("")
    for m in s.messages:
        role = "用户" if m.role == "user" else "AI 助教"
        lines.append(f"## {role}")
        lines.append("")
        lines.append(m.content or "")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def _build_pdf(s: ChatSession) -> bytes:
    """用 fpdf 将会话生成 PDF（加载 Windows 中文字体）。"""
    from fpdf import FPDF

    def pdf_text(value: str | None) -> str:
        """过滤字体无法编码的字符，避免某条消息导致整个导出接口 500。"""
        text = value or ""
        cleaned = []
        for char in text:
            code = ord(char)
            # UTF-16 代理区不是有效的独立字符，部分模型输出可能携带它。
            if 0xD800 <= code <= 0xDFFF:
                cleaned.append("□")
            elif code in (9, 10, 13) or 32 <= code <= 0xFFFF:
                cleaned.append(char)
            else:
                cleaned.append("□")
        return "".join(cleaned)

    def pdf_lines(value: str) -> list[str]:
        # 预先按字符拆分，兼容超长 URL、代码行和没有空格的中文文本。
        return textwrap.wrap(value, width=72, break_long_words=True, break_on_hyphens=False) or [""]

    class ChatPDF(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_draw_color(226, 232, 240)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.set_font(font_family, size=8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 8, f"知识智航 · 智能问答记录                                  第 {self.page_no()} 页", align="C")

    pdf = ChatPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_path = None
    for candidate in (
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simsun.ttc",
    ):
        if os.path.exists(candidate):
            font_path = candidate
            break
    if font_path:
        pdf.add_font("cn", "", font_path)
    font_family = "cn" if font_path else "helvetica"

    # 标题信息区
    pdf.set_fill_color(30, 64, 175)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(font_family, size=19)
    pdf.cell(0, 16, "  智能问答记录", ln=True, fill=True)
    pdf.set_fill_color(239, 246, 255)
    pdf.set_text_color(30, 64, 175)
    pdf.set_font(font_family, size=15)
    pdf.cell(0, 12, "  " + pdf_text(s.title), ln=True, fill=True)
    pdf.set_font(font_family, size=9)
    pdf.set_text_color(100, 116, 139)
    created = s.created_at.isoformat() if s.created_at else ""
    pdf.cell(0, 8, f"  创建时间：{created}    ·    共 {len(s.messages)} 条消息", ln=True, fill=True)
    pdf.ln(8)

    for m in s.messages:
        role = "用户" if m.role == "user" else "AI 助教"
        # 角色标签：用不同色块区分提问和回答。
        if m.role == "user":
            pdf.set_fill_color(219, 234, 254)
            pdf.set_text_color(30, 64, 175)
        else:
            pdf.set_fill_color(220, 252, 231)
            pdf.set_text_color(21, 128, 61)
        pdf.set_font(font_family, size=11)
        pdf.cell(0, 9, f"  {role}", ln=True, fill=True)
        pdf.set_text_color(51, 65, 85)
        pdf.set_font(font_family, size=10)
        pdf.ln(2)

        in_code = False
        for raw_line in pdf_text(m.content).splitlines() or [""]:
            line = raw_line.strip()
            if line.startswith("```"):
                in_code = not in_code
                continue
            if line in ("---", "***", "___"):
                pdf.set_draw_color(226, 232, 240)
                pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.w - pdf.r_margin, pdf.get_y() + 2)
                pdf.ln(5)
                continue
            if not line:
                pdf.ln(2)
                continue

            # 处理 Markdown 标题，去掉 # 符号并使用层级颜色。
            heading = re.match(r"^(#{1,6})\s+(.*)$", line)
            if heading:
                level, text = len(heading.group(1)), heading.group(2)
                text = re.sub(r"[*_`]", "", text)
                pdf.set_text_color(30, 64, 175 if level <= 2 else 100)
                pdf.set_font(font_family, size=13 if level <= 2 else 11)
                for part in pdf_lines(text):
                    pdf.multi_cell(0, 7, part, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(51, 65, 85)
                pdf.set_font(font_family, size=10)
                continue

            # 代码块使用浅灰背景，保留代码内容但不显示 Markdown 标记。
            if in_code:
                pdf.set_fill_color(248, 250, 252)
                pdf.set_text_color(51, 65, 85)
                pdf.set_font(font_family, size=9)
                for part in pdf_lines("  " + line):
                    pdf.multi_cell(0, 6, part, fill=True, new_x="LMARGIN", new_y="NEXT")
                pdf.set_font(font_family, size=10)
                continue

            # 列表、引用和粗体/斜体：转换为适合 PDF 的视觉层级。
            bullet = re.match(r"^([-*+] |\d+[.)] )(.*)$", line)
            if bullet:
                prefix, text = bullet.group(1), bullet.group(2)
                marker = "- " if not prefix[0].isdigit() else prefix
                line = "    " + marker + re.sub(r"[*_`]", "", text)
            elif line.startswith(">"):
                line = "│ " + re.sub(r"^>\s*", "", line)
                pdf.set_text_color(100, 116, 139)
            else:
                line = re.sub(r"[*_`]", "", line)
            for part in pdf_lines(line):
                pdf.multi_cell(0, 6, part, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(51, 65, 85)
        pdf.ln(7)

    # fpdf2 新版本直接返回 bytes；兼容旧版本返回 bytearray 的情况。
    output = pdf.output()
    return bytes(output)


@router.get("/sessions/{session_id}/export/markdown")
def export_markdown(session_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    s = _get_owned_session(session_id, db, u)
    md = _build_markdown(s)
    filename = quote(f"{s.title}.md")
    return Response(
        content=md.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.get("/sessions/{session_id}/export/pdf")
def export_pdf(session_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    s = _get_owned_session(session_id, db, u)
    pdf_bytes = _build_pdf(s)
    filename = quote(f"{s.title}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
