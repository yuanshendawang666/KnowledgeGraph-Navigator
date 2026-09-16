"""持久化同步标记 + 原子替换投影；SQLite 权威数据始终保留。"""
from datetime import datetime, timezone
import logging
from app.models import KnowledgePoint, KnowledgeRelation, GraphSyncState
from app.core.database import neo4j_driver


def mark_pending(db, course_id):
    state = db.get(GraphSyncState, course_id)
    if state is None:
        state = GraphSyncState(course_id=course_id)
        db.add(state)
    state.status, state.error = 'pending', ''
    state.updated_at = datetime.now(timezone.utc)


def sync_course(db, course_id):
    """在一个 Neo4j 事务中替换。失败留标记，供教师重试；不伪装跨库事务。"""
    points = db.query(KnowledgePoint).filter_by(course_id=course_id).all()
    mapping = {p.id: p.neo4j_node_id for p in points}
    nodes = [dict(neo4j_id=p.neo4j_node_id, course_id=course_id, name=p.name,
                  description=p.description or '', order_index=p.order_index or 0,
                  level=p.level, is_module=bool(p.is_module),
                  parent_id=mapping.get(p.parent_id)) for p in points]
    edges = {(mapping[r.source_kp_id], mapping[r.target_kp_id], r.relation_type.value.upper())
             for r in db.query(KnowledgeRelation).filter_by(course_id=course_id).all()
             if r.source_kp_id in mapping and r.target_kp_id in mapping}
    edges.update((p.neo4j_node_id, mapping[p.parent_id], 'PART_OF')
                 for p in points if p.parent_id in mapping)
    def replace(tx):
        tx.run('MATCH (n:KnowledgePoint {course_id:$cid}) DETACH DELETE n', cid=course_id).consume()
        tx.run('UNWIND $nodes AS item CREATE (n:KnowledgePoint) SET n = item', nodes=nodes).consume()
        tx.run('MATCH (n:KnowledgePoint {course_id:$cid}) WHERE n.is_module = true SET n:Module', cid=course_id).consume()
        for kind in ('PART_OF', 'PREREQUISITE', 'RELATED_TO'):
            rows = [dict(source=s, target=t) for s, t, k in edges if k == kind]
            tx.run(f'UNWIND $rows AS item MATCH (s:KnowledgePoint {{neo4j_id:item.source, course_id:$cid}}) '
                   f'MATCH (t:KnowledgePoint {{neo4j_id:item.target, course_id:$cid}}) MERGE (s)-[:{kind}]->(t)',
                   rows=rows, cid=course_id).consume()
    state = db.get(GraphSyncState, course_id)
    if state is None:
        mark_pending(db, course_id)
        db.flush()
        state = db.get(GraphSyncState, course_id)
    try:
        with neo4j_driver.get_session() as session:
            session.execute_write(replace)
        state.status, state.error = 'synced', ''
    except Exception:
        logging.getLogger(__name__).exception('课程 %s 图同步失败，可重试', course_id)
        state.status, state.error = 'failed', '图数据库同步失败，请检查连接后重试'
    db.commit()
    return state.status
