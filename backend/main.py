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

from app.core.config import get_settings
from app.core.database import engine, Base, neo4j_driver
from app.api import auth, courses, learning

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化数据库表，关闭时清理连接"""
    # ---- 启动时 ----
    # 创建 SQLite 表
    Base.metadata.create_all(bind=engine)

    # 确保上传目录存在
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    yield

    # ---- 关闭时 ----
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
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 注册路由 ----
app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(learning.router)


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
