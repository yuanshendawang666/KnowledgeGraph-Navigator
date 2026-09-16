"""可重复执行的 SQLite 升级；失败时阻止启动，不吞掉错误。"""
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateTable
from app.core.database import Base


def migrate(engine):
    additions = {
        "users": {"major": "VARCHAR(100) DEFAULT ''", "grade": "VARCHAR(50) DEFAULT ''",
                  "learning_goal": "VARCHAR(200) DEFAULT ''", "age_range": "VARCHAR(50) DEFAULT ''",
                  "interests": "TEXT DEFAULT '[]'", "content_preferences": "TEXT DEFAULT '[]'",
                  "onboarding_completed": "BOOLEAN DEFAULT 0"},
        "knowledge_points": {"parent_id": "INTEGER REFERENCES knowledge_points(id)",
                             "level": "INTEGER DEFAULT 2", "is_module": "BOOLEAN DEFAULT 0"},
        "classroom_tasks": {"question_ids": "TEXT NOT NULL DEFAULT '[]'"},
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            existing = {c['name'] for c in inspect(conn).get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
        # SQLite 不支持 ALTER COLUMN DROP NOT NULL，事务内重建笔记表。
        cols = inspect(conn).get_columns('notes')
        kp = next(c for c in cols if c['name'] == 'knowledge_point_id')
        if not kp['nullable']:
            ddl = str(CreateTable(Base.metadata.tables['notes']).compile(engine))
            conn.execute(text(ddl.replace('CREATE TABLE notes', 'CREATE TABLE notes_migrating', 1)))
            names = ', '.join('"' + c['name'] + '"' for c in cols)
            conn.execute(text(f'INSERT INTO notes_migrating ({names}) SELECT {names} FROM notes'))
            conn.execute(text('DROP TABLE notes'))
            conn.execute(text('ALTER TABLE notes_migrating RENAME TO notes'))
        conn.execute(text('UPDATE notes SET knowledge_point_id = NULL WHERE knowledge_point_id = 0'))
        conn.execute(text('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)'))
        conn.execute(text('INSERT OR IGNORE INTO schema_migrations(version) VALUES (1)'))
        # 未覆盖到的旧模式必须明确报错，不能带着缺列继续启动。
        for table in Base.metadata.sorted_tables:
            actual = {c['name'] for c in inspect(conn).get_columns(table.name)}
            missing = set(table.columns.keys()) - actual
            if missing:
                raise RuntimeError(f'数据库升级需要处理 {table.name} 缺失列: {sorted(missing)}')
