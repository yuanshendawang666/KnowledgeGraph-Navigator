"""数据库持久化任务，单工作线程执行；重启时恢复 queued/running。

部署约束：一个后端进程（不要使用多个 uvicorn workers）。
多实例部署应替换为有租约的外部队列。
"""
import asyncio
import json
import logging
import threading
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models import ExtractionJob, User

_stop = threading.Event()
_thread = None


def _work():
    from app.api.courses import extract_knowledge
    while not _stop.is_set():
        with SessionLocal() as db:
            job = db.query(ExtractionJob).filter_by(status='queued').order_by(ExtractionJob.created_at).first()
            if job:
                job.status = 'running'
                db.commit()
                try:
                    result = asyncio.run(extract_knowledge(job.course_id, db, db.get(User, job.user_id)))
                    job.result = json.dumps(result.model_dump(), ensure_ascii=False)
                    job.status = 'completed'
                except Exception:
                    db.rollback()
                    logging.getLogger(__name__).exception('知识抽取任务失败 %s', job.id)
                    job.status = 'failed'
                    job.error = '知识抽取失败，原有知识与学习数据已保留；请检查服务日志'
                db.commit()
        _stop.wait(1)


def start_worker():
    global _thread
    if _thread and _thread.is_alive():
        return
    with SessionLocal() as db:
        db.query(ExtractionJob).filter_by(status='running').update({'status': 'queued'})
        db.commit()
    _stop.clear()
    _thread = threading.Thread(target=_work, daemon=True, name='knowledge-extraction')
    _thread.start()


def stop_worker():
    _stop.set()
    if _thread:
        _thread.join(timeout=2)
