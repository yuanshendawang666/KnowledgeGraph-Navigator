"""
应用配置模块
-----------
集中管理所有环境变量和应用配置项，包括：
- DeepSeek API 配置
- Neo4j AuraDB 连接配置
- JWT 密钥配置
- SQLite 数据库路径
- 文件上传配置
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用配置类，自动从 .env 文件和环境变量中加载配置"""

    # ---- 应用基础配置 ----
    APP_NAME: str = "知谱智航教学系统"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ---- 数据库配置 ----
    DATABASE_URL: str = "sqlite:///./knowledge_navigator.db"

    # ---- Neo4j AuraDB 配置 ----
    NEO4J_URI: str = "neo4j+s://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"

    # ---- DeepSeek API 配置 ----
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # ---- JWT 认证配置 ----
    SECRET_KEY: str = "change-me-to-a-secure-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # ---- 文件上传配置 ----
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # ---- RAG 配置 ----
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例（带缓存）"""
    return Settings()
