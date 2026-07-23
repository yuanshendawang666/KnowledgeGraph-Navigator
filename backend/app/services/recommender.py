"""
个性化学习路径推荐服务
--------------------------
基于知识图谱中的先修关系（PREREQUISITE），使用拓扑排序算法，
结合用户的学习进度，生成个性化的学习路径推荐。

核心算法：
1. 从 Neo4j 获取课程的先修依赖图（DAG）
2. 构建拓扑排序得到合法的学习顺序
3. 排除用户已掌握的知识点
4. 推荐"可立即学习"的知识点（所有先修条件已满足）
5. 生成完整的学习路径（包含已掌握和待学习的知识点）

使用方式：
    from app.services.recommender import LearningPathRecommender
    recommender = LearningPathRecommender()
    path = recommender.recommend_path(course_id, user_id)
"""

from collections import deque
from typing import List, Dict, Set

from app.core.database import SessionLocal
from app.models import KnowledgeStatus, UserKnowledgeProgress
from app.services.graph_ops import GraphOperations


class LearningPathRecommender:
    """
    学习路径推荐器
    基于拓扑排序和用户进度生成个性化推荐
    """

    def __init__(self):
        self.graph_ops = GraphOperations()

    def recommend_path(
        self,
        course_id: int,
        user_id: int,
    ) -> Dict:
        """
        为用户生成课程的学习路径推荐。

        Args:
            course_id: 课程 ID
            user_id: 用户 ID

        Returns:
            {
                "all_knowledge_points": [...],    # 拓扑排序后的完整知识点列表
                "mastered_ids": [...],            # 已掌握的 neo4j_id 集合
                "in_progress_ids": [...],         # 正在学习的 neo4j_id 集合
                "ready_to_learn": [...],          # 当前可学习（所有先修已满足）
                "recommended_next": [...],        # 推荐立即开始学习的前 5 个
                "progress_percentage": 0.0,       # 整体学习进度百分比
                "total_count": 0,                 # 知识点总数
                "mastered_count": 0,              # 已掌握数
            }
        """
        # 1. 从 Neo4j 获取课程的知识图谱
        graph_data = self.graph_ops.get_course_graph(course_id)
        nodes = graph_data["nodes"]
        edges = graph_data["edges"]

        if not nodes:
            return {
                "all_knowledge_points": [],
                "mastered_ids": [],
                "in_progress_ids": [],
                "ready_to_learn": [],
                "recommended_next": [],
                "progress_percentage": 0.0,
                "total_count": 0,
                "mastered_count": 0,
            }

        # 2. 构建邻接表和入度表（仅限 PREREQUISITE 关系）
        adjacency: Dict[str, List[str]] = {}  # source → [targets]
        in_degree: Dict[str, int] = {node["id"]: 0 for node in nodes}

        for edge in edges:
            if edge["relation"] == "PREREQUISITE":
                src = edge["source"]
                tgt = edge["target"]
                if src not in adjacency:
                    adjacency[src] = []
                adjacency[src].append(tgt)
                in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # 确保所有节点都在 adjacency 中
        for node in nodes:
            if node["id"] not in adjacency:
                adjacency[node["id"]] = []

        # 3. 获取用户的学习进度
        user_progress = self._get_user_progress(user_id, course_id)

        # 4. 拓扑排序
        sorted_kps = self._topological_sort(nodes, adjacency, in_degree)

        # 5. 确定可学习的知识点
        mastered_ids: Set[str] = set()
        in_progress_ids: Set[str] = set()

        # 创建 neo4j_id → node 的映射
        node_map = {n["id"]: n for n in nodes}

        for kp_id, progress in user_progress.items():
            if progress["status"] == KnowledgeStatus.MASTERED.value:
                mastered_ids.add(kp_id)
            elif progress["status"] == KnowledgeStatus.IN_PROGRESS.value:
                in_progress_ids.add(kp_id)

        # 6. 找出当前可学习的知识点
        #    条件：(a) 未掌握且未在学习中, (b) 所有先修知识点已掌握
        ready_to_learn = []

        for kp in sorted_kps:
            kp_id = kp["id"]
            if kp_id in mastered_ids or kp_id in in_progress_ids:
                continue

            # 检查所有先修条件是否已满足
            prerequisites_met = True
            for edge in edges:
                if (edge["relation"] == "PREREQUISITE"
                        and edge["target"] == kp_id):
                    if edge["source"] not in mastered_ids:
                        prerequisites_met = False
                        break

            if prerequisites_met:
                ready_to_learn.append(kp)

        # 7. 生成推荐：优先取 ready_to_learn 中的前 5 个
        recommended_next = ready_to_learn[:5]

        # 8. 计算进度统计
        total_count = len(nodes)
        mastered_count = len(mastered_ids)

        # 更细致的进度：正在学习的计为 0.5
        in_progress_weight = len(in_progress_ids) * 0.5
        progress_percentage = (
            ((mastered_count + in_progress_weight) / total_count * 100)
            if total_count > 0
            else 0.0
        )
        progress_percentage = round(progress_percentage, 1)

        return {
            "all_knowledge_points": sorted_kps,
            "mastered_ids": list(mastered_ids),
            "in_progress_ids": list(in_progress_ids),
            "ready_to_learn": ready_to_learn,
            "recommended_next": recommended_next,
            "progress_percentage": progress_percentage,
            "total_count": total_count,
            "mastered_count": mastered_count,
        }

    def _topological_sort(
        self,
        nodes: List[Dict],
        adjacency: Dict[str, List[str]],
        in_degree: Dict[str, int],
    ) -> List[Dict]:
        """
        使用 Kahn 算法对有向无环图进行拓扑排序。
        遇到环时，按 order_index 打破平局。

        Returns:
            按拓扑顺序排列的知识点列表
        """
        node_map = {n["id"]: n for n in nodes}

        # 初始化队列：入度为 0 的节点，按 order_index 排序
        queue = deque()
        zero_in_degree = sorted(
            [nid for nid, deg in in_degree.items() if deg == 0],
            key=lambda nid: node_map.get(nid, {}).get("order_index", 0),
        )
        queue.extend(zero_in_degree)

        sorted_result = []
        temp_in_degree = dict(in_degree)

        while queue:
            current = queue.popleft()
            if current in node_map:
                sorted_result.append(node_map[current])

            for neighbor in adjacency.get(current, []):
                temp_in_degree[neighbor] -= 1
                if temp_in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 如果还有未排序的节点（存在环），按 order_index 追加
        sorted_ids = {n["id"] for n in sorted_result}
        remaining = [n for n in nodes if n["id"] not in sorted_ids]
        remaining.sort(key=lambda n: n.get("order_index", 0))
        sorted_result.extend(remaining)

        return sorted_result

    def _get_user_progress(
        self,
        user_id: int,
        course_id: int,
    ) -> Dict[str, Dict]:
        """
        从 SQLite 获取用户对课程知识点的学习进度。

        Returns:
            {neo4j_node_id: {"status": "mastered", "mastery_level": 1.0}, ...}
        """
        db = SessionLocal()
        try:
            # 查询该课程下所有知识点
            from app.models import KnowledgePoint

            kps = (
                db.query(KnowledgePoint)
                .filter(KnowledgePoint.course_id == course_id)
                .all()
            )

            # 查询用户的学习进度
            kp_ids = [kp.id for kp in kps]
            progress_records = (
                db.query(UserKnowledgeProgress)
                .filter(
                    UserKnowledgeProgress.user_id == user_id,
                    UserKnowledgeProgress.knowledge_point_id.in_(kp_ids),
                )
                .all()
            )

            # 构建映射: SQLite kp_id → status
            progress_map = {
                p.knowledge_point_id: {
                    "status": p.status.value if p.status else "not_started",
                    "mastery_level": p.mastery_level,
                }
                for p in progress_records
            }

            # 转换为: neo4j_id → status
            result = {}
            for kp in kps:
                if kp.neo4j_node_id:
                    if kp.id in progress_map:
                        result[kp.neo4j_node_id] = progress_map[kp.id]
                    else:
                        result[kp.neo4j_node_id] = {
                            "status": "not_started",
                            "mastery_level": 0.0,
                        }

            return result
        finally:
            db.close()


# 便捷函数
def get_recommended_path(course_id: int, user_id: int) -> Dict:
    """获取推荐学习路径的便捷函数"""
    recommender = LearningPathRecommender()
    return recommender.recommend_path(course_id, user_id)
