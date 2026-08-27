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
        level: int = 2,
        is_module: bool = False,
    ) -> Dict:
        """
        在 Neo4j 中创建一个知识点/模块节点。

        level=0 根模块, level=1 子模块, level=2 叶子知识点
        """
        node_id = neo4j_id or f"kp_{course_id}_{order_index}"
        labels = "KnowledgePoint:Module" if is_module else "KnowledgePoint"
        result = run_cypher(
            f"""
            CREATE (kp:{labels} {{
                neo4j_id: $neo4j_id,
                name: $name,
                description: $description,
                course_id: $course_id,
                order_index: $order_index,
                level: $level,
                is_module: $is_module
            }})
            RETURN kp
            """,
            {
                "neo4j_id": node_id,
                "name": name,
                "description": description,
                "course_id": course_id,
                "order_index": order_index,
                "level": level,
                "is_module": is_module,
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
        """批量创建知识点节点，支持树状层级。"""
        results = []
        for i, kp in enumerate(knowledge_points):
            neo4j_id = f"kp_{course_id}_{kp.get('order_index', i)}"
            node = GraphOperations.create_knowledge_point(
                name=kp["name"],
                description=kp.get("description", ""),
                course_id=course_id,
                order_index=kp.get("order_index", i),
                neo4j_id=neo4j_id,
                level=kp.get("level", 2),
                is_module=kp.get("is_module", False),
            )
            if node:
                results.append(node)
        return results

    @staticmethod
    def bulk_create_tree(course_id: int, modules: List[Dict]) -> Dict:
        """
        创建树状知识结构：模块 → 子模块 → 知识点。
        同时创建 PART_OF 关系连接父子节点。
        """
        node_index = 0
        all_nodes = []

        for mod in modules:
            # 根模块
            mod_id = f"kp_{course_id}_m{node_index}"
            node_index += 1
            GraphOperations.create_knowledge_point(
                name=mod["name"], description=mod.get("description", ""),
                course_id=course_id, order_index=mod.get("order_index", 0),
                neo4j_id=mod_id, level=0, is_module=True,
            )
            all_nodes.append(mod_id)

            for sub in mod.get("sub_modules", []):
                sub_id = f"kp_{course_id}_m{node_index}"
                node_index += 1
                GraphOperations.create_knowledge_point(
                    name=sub["name"], description=sub.get("description", ""),
                    course_id=course_id, order_index=sub.get("order_index", 0),
                    neo4j_id=sub_id, level=1, is_module=True,
                )
                all_nodes.append(sub_id)
                # 子模块 → 父模块
                GraphOperations.create_relation(sub_id, mod_id, "part_of")

                for kp in sub.get("knowledge_points", []):
                    kp_id = f"kp_{course_id}_m{node_index}"
                    node_index += 1
                    GraphOperations.create_knowledge_point(
                        name=kp["name"], description=kp.get("description", ""),
                        course_id=course_id, order_index=kp.get("order_index", 0),
                        neo4j_id=kp_id, level=2, is_module=False,
                    )
                    all_nodes.append(kp_id)
                    # 知识点 → 子模块
                    GraphOperations.create_relation(kp_id, sub_id, "part_of")

        return {"node_count": node_index, "nodes": all_nodes}

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
        获取课程的知识图谱，返回**树状结构**数据。

        分层设计：
          - Module 节点 (level 0/1): 大节点、深色、作为容器
          - Leaf 节点 (level 2): 小节点、浅色、叶子
          - PART_OF 边: 细虚线，表示层级归属
          - PREREQUISITE 边: 粗实线，表示跨模块学习依赖

        Returns:
            {
                "nodes": [{"id", "label", "level", "is_module", "parent_id", ...}],
                "edges": [{"source", "target", "relation"}, ...],
                "tree": [{module with children}]   // 树状结构用于前端渲染
            }
        """
        nodes_result = run_cypher(
            """
            MATCH (kp:KnowledgePoint {course_id: $course_id})
            RETURN kp ORDER BY coalesce(kp.level, 2), kp.order_index
            """,
            {"course_id": course_id},
        )

        edges_result = run_cypher(
            """
            MATCH (a:KnowledgePoint {course_id: $course_id})-[r]->(b:KnowledgePoint {course_id: $course_id})
            RETURN a.neo4j_id as source, b.neo4j_id as target, type(r) as relation
            """,
            {"course_id": course_id},
        )

        # 构建节点，附加上 parent_id
        node_map = {}
        nodes = []
        for record in nodes_result:
            kp = record["kp"]
            n = {
                "id": kp["neo4j_id"],
                "label": kp["name"],
                "description": kp.get("description", ""),
                "order_index": kp.get("order_index", 0),
                "level": kp.get("level", 2),
                "is_module": kp.get("is_module", False),
                "parent_id": None,  # 稍后从 PART_OF 边推导
            }
            node_map[n["id"]] = n
            nodes.append(n)

        # 分类边，并简化跨模块边
        tree_edges = []
        cross_edges_raw = []
        for record in edges_result:
            edge = {
                "source": record["source"],
                "target": record["target"],
                "relation": record["relation"],
            }
            if record["relation"] == "PART_OF":
                tree_edges.append(edge)
                if edge["source"] in node_map:
                    node_map[edge["source"]]["parent_id"] = edge["target"]
            else:
                cross_edges_raw.append(edge)

        # 简化跨模块边：只保留模块间的 PREREQUISITE，去除知识点间的
        cross_edges = GraphOperations._simplify_edges(cross_edges_raw, node_map)

        # 构建树 (从根模块开始)
        def build_tree(parent_id=None):
            children = []
            for n in nodes:
                if n["parent_id"] == parent_id:
                    children.append({
                        **n,
                        "children": build_tree(n["id"]),
                    })
            return sorted(children, key=lambda x: x["order_index"])

        tree = build_tree(None)
        # 如果所有节点都没有 parent_id（旧数据），回退到 flat 列表
        if not tree and nodes:
            tree = [{"id": "root", "label": "知识图谱", "level": -1, "is_module": True, "children": [dict(n, children=[]) for n in nodes]}]

        return {
            "nodes": nodes,
            "edges": tree_edges + cross_edges,
            "tree_edges": tree_edges,
            "cross_edges": cross_edges,
            "tree": tree,
        }

    @staticmethod
    def _simplify_edges(edges: List[Dict], node_map: Dict) -> List[Dict]:
        """
        简化跨模块边：
        1. 只保留模块节点间的 PREREQUISITE（移除知识点/子模块间的）
        2. 去除传递闭包边（A→B 且 B→C 且 A→C → 删除 A→C）
        3. 去重双向边
        """
        if not edges:
            return []

        # Step 1: 将知识点级的边提升到所属模块
        def get_module_id(node_id: str) -> str:
            """向上追溯到根模块"""
            current = node_id
            while current in node_map and node_map[current].get("parent_id"):
                current = node_map[current]["parent_id"]
            return current

        module_edges: Dict[str, dict] = {}  # key="src_mod→tgt_mod" → edge
        for edge in edges:
            if edge["relation"] != "PREREQUISITE":
                continue
            src_mod = get_module_id(edge["source"])
            tgt_mod = get_module_id(edge["target"])
            if src_mod == tgt_mod:
                continue  # 同模块内的忽略
            key = f"{src_mod}→{tgt_mod}"
            if key not in module_edges:
                module_edges[key] = {"source": src_mod, "target": tgt_mod, "relation": "PREREQUISITE"}

        result = list(module_edges.values())

        # Step 2: 去除传递边 (A→C 如果存在 A→B 且 B→C)
        if len(result) <= 1:
            return result

        # 构建可达性矩阵
        nodes_set = set()
        for e in result:
            nodes_set.add(e["source"])
            nodes_set.add(e["target"])

        # Floyd-Warshall 找传递闭包
        reachable: Dict[str, set] = {n: set() for n in nodes_set}
        for e in result:
            reachable[e["source"]].add(e["target"])

        # 传递闭包
        changed = True
        while changed:
            changed = False
            for k in nodes_set:
                for i in nodes_set:
                    if k in reachable.get(i, set()):
                        for j in list(reachable.get(k, set())):
                            if j not in reachable.get(i, set()):
                                reachable[i].add(j)
                                changed = True

        # 删除间接边
        simplified = []
        for e in result:
            is_direct = True
            for mid in nodes_set:
                if mid == e["source"] or mid == e["target"]:
                    continue
                # 如果 source→mid 且 mid→target，则 source→target 是间接的
                if (mid in reachable.get(e["source"], set()) and
                    e["target"] in reachable.get(mid, set())):
                    is_direct = False
                    break
            if is_direct:
                simplified.append(e)

        return simplified

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
