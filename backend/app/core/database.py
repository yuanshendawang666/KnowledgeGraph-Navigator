"""
数据库连接管理模块
------------------
管理 SQLite（关系型数据）和 Neo4j（图数据）两种数据库连接：
- SQLite: 存储用户、课程、学习进度等结构化数据
- Neo4j: 存储知识图谱的节点和关系

提供连接获取、会话管理、以及图数据库操作的工具函数。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from neo4j import GraphDatabase

from app.core.config import get_settings

settings = get_settings()

# ============================================================
# SQLite 关系型数据库
# ============================================================

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite 需要此参数
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取 SQLite 数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# Neo4j 图数据库
# ============================================================

class Neo4jDriver:
    """Neo4j 驱动单例，管理连接池"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._driver = None
        return cls._instance

    @property
    def driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
        return self._driver

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None

    def get_session(self):
        """获取一个 Neo4j 会话"""
        return self.driver.session()


neo4j_driver = Neo4jDriver()


def get_neo4j():
    """FastAPI 依赖注入：获取 Neo4j 会话"""
    session = neo4j_driver.get_session()
    try:
        yield session
    finally:
        session.close()


def run_cypher(query: str, params: dict = None) -> list:
    """
    执行 Cypher 查询并返回结果列表。
    用于服务层中的非 API 调用场景。
    """
    with neo4j_driver.get_session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]
