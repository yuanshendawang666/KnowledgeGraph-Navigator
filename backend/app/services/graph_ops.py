"""
图数据库操作服务
----------------
封装 Neo4j 图数据库的 CRUD 操作，管理知识图谱的节点和关系。

核心操作：
- 创建/更新/删除知识点节点
- 创建/更新/删除知识点关系
- 查询课程的知识图谱（节点+边，用于前端可视化）
- 拓扑排序查询（从入度为零的节点开始的依赖链）

图数据模型：
    (:KnowledgePoint {neo4j_id, name, description, course_id, order_index})
    [:PREREQUISITE]   — A 是 B 的先修知识点
    [:RELATED_TO]     — A 与 B 相关
    [:PART_OF]        — A 是 B 的组成部分

使用方式：
    from app.services.graph_ops import GraphOperations
    gops = GraphOperations()
    gops.create_knowledge_point(...)
"""

from typing import List, Dict, Optional
from neo4j import Session

from app.core.database import run_cypher


class GraphOperations:
    """Neo4j 知识图谱操作封装"""

    # ---- 知识点节点操作 ----

    @staticmethod
    def create_knowledge_point(
        name: str,
        description: str,
        course_id: int,
        order_index: int = 0,
        neo4j_id: str = None,
    ) -> Dict:
        """
        在 Neo4j 中创建一个知识点节点。

        Args:
            name: 知识点名称
            description: 知识点描述
            course_id: 所属课程 ID
            order_index: 排序索引
            neo4j_id: 自定义 Neo4j 节点 ID

        Returns:
            创建的节点数据
        """
        node_id = neo4j_id or f"kp_{course_id}_{order_index}"
        result = run_cypher(
            """
            CREATE (kp:KnowledgePoint {
                neo4j_id: $neo4j_id,
                name: $name,
                description: $description,
                course_id: $course_id,
                order_index: $order_index
            })
            RETURN kp
            """,
            {
                "neo4j_id": node_id,
                "name": name,
                "description": description,
                "course_id": course_id,
                "order_index": order_index,
            },
        )
        return result[0]["kp"] if result else None

    @staticmethod
    def get_knowledge_point(neo4j_id: str) -> Optional[Dict]:
        """根据 neo4j_id 查询知识点节点"""
        result = run_cypher(
            "MATCH (kp:KnowledgePoint {neo4j_id: $neo4j_id}) RETURN kp",
            {"neo4j_id": neo4j_id},
        )
        return result[0]["kp"] if result else None

    @staticmethod
    def update_knowledge_point(
        neo4j_id: str,
        name: str = None,
        description: str = None,
        order_index: int = None,
    ) -> Optional[Dict]:
        """更新知识点节点属性"""
        set_clauses = []
        params = {"neo4j_id": neo4j_id}

        if name is not None:
            set_clauses.append("kp.name = $name")
            params["name"] = name
        if description is not None:
            set_clauses.append("kp.description = $description")
            params["description"] = description
        if order_index is not None:
            set_clauses.append("kp.order_index = $order_index")
            params["order_index"] = order_index

        if not set_clauses:
            return GraphOperations.get_knowledge_point(neo4j_id)

        result = run_cypher(
            f"""
            MATCH (kp:KnowledgePoint {{neo4j_id: $neo4j_id}})
            SET {', '.join(set_clauses)}
            RETURN kp
            """,
            params,
        )
        return result[0]["kp"] if result else None

    @staticmethod
    def delete_knowledge_point(neo4j_id: str) -> bool:
        """删除知识点节点及其所有关系"""
        result = run_cypher(
            """
            MATCH (kp:KnowledgePoint {neo4j_id: $neo4j_id})
            DETACH DELETE kp
            RETURN count(kp) as deleted_count
            """,
            {"neo4j_id": neo4j_id},
        )
        return result[0]["deleted_count"] > 0 if result else False

    @staticmethod
    def get_course_knowledge_points(course_id: int) -> List[Dict]:
        """获取课程的所有知识点节点"""
        result = run_cypher(
            """
            MATCH (kp:KnowledgePoint {course_id: $course_id})
            RETURN kp
            ORDER BY kp.order_index
            """,
            {"course_id": course_id},
        )
        return [r["kp"] for r in result]

    @staticmethod
    def bulk_create_knowledge_points(
        knowledge_points: List[Dict],
        course_id: int,
    ) -> List[Dict]:
        """
        批量创建知识点节点。

        Args:
            knowledge_points: [{"name": ..., "description": ..., "order_index": ...}, ...]
            course_id: 所属课程 ID

        Returns:
            创建的所有节点数据
        """
        results = []
        for i, kp in enumerate(knowledge_points):
            neo4j_id = f"kp_{course_id}_{kp.get('order_index', i)}"
            node = GraphOperations.create_knowledge_point(
                name=kp["name"],
                description=kp.get("description", ""),
                course_id=course_id,
                order_index=kp.get("order_index", i),
                neo4j_id=neo4j_id,
            )
            if node:
                results.append(node)
        return results

    # ---- 关系操作 ----

    @staticmethod
    def create_relation(
        source_neo4j_id: str,
        target_neo4j_id: str,
        relation_type: str,
    ) -> Optional[Dict]:
        """
        在两个知识点之间创建关系。

        Args:
            source_neo4j_id: 源知识点 neo4j_id
            target_neo4j_id: 目标知识点 neo4j_id
            relation_type: 关系类型 (PREREQUISITE, RELATED_TO, PART_OF)

        Returns:
            关系信息
        """
        # 将 relation_type 映射为大写的关系类型
        rel_type_map = {
            "prerequisite": "PREREQUISITE",
            "related_to": "RELATED_TO",
            "part_of": "PART_OF",
        }
        rel_type = rel_type_map.get(relation_type, "RELATED_TO")

        result = run_cypher(
            f"""
            MATCH (a:KnowledgePoint {{neo4j_id: $source_id}})
            MATCH (b:KnowledgePoint {{neo4j_id: $target_id}})
            MERGE (a)-[r:{rel_type}]->(b)
            RETURN a, r, b
            """,
            {"source_id": source_neo4j_id, "target_id": target_neo4j_id},
        )
        return result[0] if result else None

    @staticmethod
    def delete_relation(
        source_neo4j_id: str,
        target_neo4j_id: str,
        relation_type: str = None,
    ) -> bool:
        """删除知识点之间的关系"""
        rel_type_map = {
            "prerequisite": "PREREQUISITE",
            "related_to": "RELATED_TO",
            "part_of": "PART_OF",
        }

        if relation_type and relation_type in rel_type_map:
            rel_clause = f":{rel_type_map[relation_type]}"
        else:
            rel_clause = ""

        result = run_cypher(
            f"""
            MATCH (a:KnowledgePoint {{neo4j_id: $source_id}})
            -[r{rel_clause}]->
            (b:KnowledgePoint {{neo4j_id: $target_id}})
            DELETE r
            RETURN count(r) as deleted_count
            """,
            {"source_id": source_neo4j_id, "target_id": target_neo4j_id},
        )
        return result[0]["deleted_count"] > 0 if result else False

    @staticmethod
    def bulk_create_relations(
        relations: List[Dict],
        course_id: int,
    ) -> List[Dict]:
        """
        批量创建知识点关系。
        关系中使用知识点名称，需先在 Neo4j 中查找对应的节点。

        Args:
            relations: [{"source": "源名称", "target": "目标名称",
                         "relation_type": "prerequisite"}, ...]
            course_id: 课程 ID

        Returns:
            成功创建的关系列表
        """
        results = []
        for rel in relations:
            # 先查找源和目标节点的 neo4j_id
            source_result = run_cypher(
                """
                MATCH (kp:KnowledgePoint {name: $name, course_id: $course_id})
                RETURN kp.neo4j_id as neo4j_id
                LIMIT 1
                """,
                {"name": rel["source"], "course_id": course_id},
            )
            target_result = run_cypher(
                """
                MATCH (kp:KnowledgePoint {name: $name, course_id: $course_id})
                RETURN kp.neo4j_id as neo4j_id
                LIMIT 1
                """,
                {"name": rel["target"], "course_id": course_id},
            )

            if source_result and target_result:
                result = GraphOperations.create_relation(
                    source_neo4j_id=source_result[0]["neo4j_id"],
                    target_neo4j_id=target_result[0]["neo4j_id"],
                    relation_type=rel["relation_type"],
                )
                if result:
                    results.append(result)

        return results

    # ---- 图查询操作 ----

    @staticmethod
    def get_course_graph(course_id: int) -> Dict:
        """
        获取课程的完整知识图谱数据（节点和边），
        返回格式适合前端 AntV G6 可视化。

        Returns:
            {
                "nodes": [{"id": "neo4j_id", "label": "名称",
                           "description": "...", "order_index": 0}, ...],
                "edges": [{"source": "neo4j_id", "target": "neo4j_id",
                           "relation": "PREREQUISITE"}, ...]
            }
        """
        # 查询所有知识点节点
        nodes_result = run_cypher(
            """
            MATCH (kp:KnowledgePoint {course_id: $course_id})
            RETURN kp
            ORDER BY kp.order_index
            """,
            {"course_id": course_id},
        )

        # 查询所有关系边
        edges_result = run_cypher(
            """
            MATCH (a:KnowledgePoint {course_id: $course_id})
            -[r]->
            (b:KnowledgePoint {course_id: $course_id})
            RETURN a.neo4j_id as source, b.neo4j_id as target,
                   type(r) as relation
            """,
            {"course_id": course_id},
        )

        nodes = []
        for record in nodes_result:
            kp = record["kp"]
            nodes.append({
                "id": kp["neo4j_id"],
                "label": kp["name"],
                "description": kp.get("description", ""),
                "order_index": kp.get("order_index", 0),
            })

        edges = []
        for record in edges_result:
            edges.append({
                "source": record["source"],
                "target": record["target"],
                "relation": record["relation"],
            })

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def get_prerequisite_graph(course_id: int) -> Dict[str, List[str]]:
        """
        获取课程的先修关系依赖图（邻接表形式）。

        Returns:
            {kp_neo4j_id: [neo4j_id of dependent KPs], ...}
            即：key 是先修知识点，value 是依赖它的知识点列表。
            如果 A→B（A 是 B 的先修），则 A 在 key，B 在 value 列表中。
        """
        edges_result = run_cypher(
            """
            MATCH (a:KnowledgePoint {course_id: $course_id})
            -[:PREREQUISITE]->
            (b:KnowledgePoint {course_id: $course_id})
            RETURN a.neo4j_id as source, b.neo4j_id as target
            """,
            {"course_id": course_id},
        )

        graph: Dict[str, List[str]] = {}
        for record in edges_result:
            source = record["source"]
            target = record["target"]
            if source not in graph:
                graph[source] = []
            graph[source].append(target)

        return graph

    @staticmethod
    def get_node_in_degrees(course_id: int) -> Dict[str, int]:
        """
        获取每个节点的入度（有多少个先修知识点）。

        Returns:
            {kp_neo4j_id: in_degree, ...}
        """
        result = run_cypher(
            """
            MATCH (kp:KnowledgePoint {course_id: $course_id})
            OPTIONAL MATCH (kp)<-[:PREREQUISITE]-(prereq:KnowledgePoint)
            RETURN kp.neo4j_id as neo4j_id, count(prereq) as in_degree
            """,
            {"course_id": course_id},
        )
        return {r["neo4j_id"]: r["in_degree"] for r in result}

    @staticmethod
    def clear_course_graph(course_id: int) -> int:
        """清除课程的所有图数据，返回删除的节点数"""
        result = run_cypher(
            """
            MATCH (kp:KnowledgePoint {course_id: $course_id})
            DETACH DELETE kp
            RETURN count(kp) as deleted_count
            """,
            {"course_id": course_id},
        )
        return result[0]["deleted_count"] if result else 0
