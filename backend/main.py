"""
知谱智航教学系统 — FastAPI 应用入口
=====================================

基于知识图谱的智能教学平台后端服务。

功能模块：
- 用户认证 (JWT)
- 课程与知识图谱管理
- 学习进度追踪
- 个性化学习路径推荐
- 智能问答 (RAG)

启动方式：
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import engine, Base, neo4j_driver
from app.api import auth, courses, learning, qa, quiz, chat, notes, classroom, knowledge, evaluate

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库表，关闭时清理连接"""
    # ---- 启动时 ----
    # 创建 SQLite 表（新表）
    Base.metadata.create_all(bind=engine)

    # 轻量迁移：为已存在的 users 表补充画像列（SQLite create_all 不会为已有表加列）
    from app.core.migrations import migrate
    migrate(engine)
    from app.services.extraction_jobs import start_worker, stop_worker
    start_worker()

    # 确保上传目录存在
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    yield

    # ---- 关闭时 ----
    stop_worker()
    neo4j_driver.close()




app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于大语言模型的知识图谱教学平台",
    lifespan=lifespan,
)

# ---- CORS 中间件 ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 注册路由 ----
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(learning.router)
app.include_router(qa.router)
app.include_router(quiz.router)
app.include_router(chat.router)
app.include_router(notes.router)
app.include_router(classroom.router)
app.include_router(knowledge.router)
app.include_router(evaluate.router)

# ---- 静态文件 (仪表盘等) ----
import os
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")


# ---- 健康检查 ----
@app.get("/")
def root():
    """应用健康检查"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health_check():
    """详细健康检查"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
