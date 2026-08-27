"""
个性化推荐增强服务 (功能1)
--------------------------
在原拓扑排序推荐的基础上，融合用户画像（专业/年级/学习目标）、
学习行为与图谱拓扑，返回带「推荐理由 + 置信度 + 预计时长」的推荐列表。

与 recommender.py（课程级 Top5）的关系：
  - recommender.py 负责核心拓扑排序 + 可学知识点判定
  - recommender_v2.py 在其结果上叠加多维度理由与评分
"""

from typing import Dict, List, Optional

from app.core.database import SessionLocal
from app.models import User, KnowledgePoint, UserKnowledgeProgress
from app.services.recommender import LearningPathRecommender
from app.services.graph_ops import GraphOperations


class EnhancedRecommender:
    """多维度推荐器（画像 + 拓扑 + 行为）。"""

    def __init__(self):
        self.base = LearningPathRecommender()
        self.graph_ops = GraphOperations()

    def recommend_v2(self, course_id: int, user_id: int) -> Dict:
        """返回带理由的推荐列表。"""
        base = self.base.recommend_path(course_id, user_id)
        ready = base.get("ready_to_learn", []) or []
        mastered_ids = set(base.get("mastered_ids", []))

        user = self._get_user(user_id)
        behavior = self._get_behavior(user_id, course_id)

        # 用户画像用于「专业路径」提示
        profile_note = self._build_profile_note(user, behavior)

        recommendations: List[Dict] = []
        for kp in ready[:6]:
            reason, confidence = self._build_reason(kp, mastered_ids, behavior, course_id)
            recommendations.append({
                "id": kp.get("id"),
                "name": kp.get("label") or kp.get("name"),
                "description": kp.get("description", ""),
                "reason": reason,
                "confidence": confidence,
                "estimated_minutes": self._estimate_minutes(kp),
            })

        return {
            "course_id": course_id,
            "profile_note": profile_note,
            "total_count": base.get("total_count", 0),
            "mastered_count": base.get("mastered_count", 0),
            "progress_percentage": base.get("progress_percentage", 0.0),
            "recommendations": recommendations,
        }

    # ---- 内部 ----

    @staticmethod
    def _get_user(user_id: int) -> Optional[User]:
        db = SessionLocal()
        try:
            return db.query(User).filter(User.id == user_id).first()
        finally:
            db.close()

    @staticmethod
    def _get_behavior(user_id: int, course_id: int) -> Dict:
        """从行为日志聚合学习时长与答题正确率。"""
        from app.models import LearningBehavior
        db = SessionLocal()
        try:
            rows = db.query(LearningBehavior).filter(
                LearningBehavior.user_id == user_id,
                LearningBehavior.course_id == course_id,
            ).all()
            total_seconds = sum(r.duration_seconds or 0 for r in rows)
            quiz_rows = [r for r in rows if r.action == "quiz"]
            attempts = len(quiz_rows)
            corrects = sum(1 for r in quiz_rows if (r.score or 0) >= 0.6)
            return {
                "study_minutes": round(total_seconds / 60.0, 1),
                "attempt_count": attempts,
                "correct_rate": round(corrects / attempts, 2) if attempts else None,
            }
        finally:
            db.close()

    def _build_reason(self, kp: Dict, mastered_ids: set, behavior: Dict, course_id: int) -> tuple:
        """根据图谱拓扑与用户状态生成推荐理由与置信度。"""
        kp_id = kp.get("id")
        # 关联拓展：该知识点与某个已掌握知识点相关
        try:
            graph = self.graph_ops.get_course_graph(course_id)
            edges = graph.get("edges", [])
            related_mastered = [
                e for e in edges
                if e.get("relation") in ("RELATED_TO", "PREREQUISITE")
                and ((e.get("source") == kp_id and e.get("target") in mastered_ids)
                     or (e.get("target") == kp_id and e.get("source") in mastered_ids))
            ]
        except Exception:
            related_mastered = []

        if related_mastered:
            reason = "与你已掌握的知识点相关联，可顺势拓展学习"
            confidence = 0.85
        elif kp.get("level", 2) == 2:
            reason = "先修条件已满足，可直接开始学习"
            confidence = 0.75
        else:
            reason = "作为模块入口，建议优先掌握"
            confidence = 0.7

        # 行为数据：答题正确率偏低 → 强化基础建议
        if behavior.get("correct_rate") is not None and behavior["correct_rate"] < 0.6:
            reason += "（近期正确率偏低，建议放慢节奏、先巩固基础）"
            confidence = max(0.4, confidence - 0.1)

        return reason, round(confidence, 2)

    @staticmethod
    def _estimate_minutes(kp: Dict) -> int:
        """根据描述长度粗略估计学习时长（分钟）。"""
        desc_len = len(kp.get("description") or "")
        return min(60, max(5, 8 + desc_len // 20))

    @staticmethod
    def _build_profile_note(user: Optional[User], behavior: Dict) -> str:
        parts = []
        if user:
            if user.major:
                parts.append(f"专业：{user.major}")
            if user.grade:
                parts.append(f"年级：{user.grade}")
            if user.learning_goal:
                parts.append(f"目标：{user.learning_goal}")
        if behavior.get("study_minutes"):
            parts.append(f"累计学习 {int(behavior['study_minutes'])} 分钟")
        return "，".join(parts) + "。" if parts else ""


def get_enhanced_recommender() -> EnhancedRecommender:
    return EnhancedRecommender()
