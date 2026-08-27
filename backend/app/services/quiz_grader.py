"""
练习题判分服务
--------------
客观题（单选 / 多选 / 判断）规则判分。
"""

from app.models import QuestionType


def normalize_choice_answer(answer: str) -> str:
    """规范化选择题答案：提取字母并排序"""
    letters = sorted(c for c in answer.upper() if c in "ABCDEF")
    return ",".join(letters)


def grade_answer(question_type: QuestionType, correct: str, user: str) -> bool:
    """判断单题是否正确"""
    user = (user or "").strip()
    correct = (correct or "").strip()

    if not user:
        return False

    if question_type == QuestionType.TRUE_FALSE:
        u = user.lower()
        c = correct.lower()
        true_vals = {"true", "正确", "对", "是", "t", "1"}
        false_vals = {"false", "错误", "错", "否", "f", "0"}
        user_bool = u in true_vals or u == "true"
        user_false = u in false_vals or u == "false"
        if user_bool and not user_false:
            return c in ("true", "正确")
        if user_false and not user_bool:
            return c in ("false", "错误")
        return False

    if question_type == QuestionType.MULTIPLE_CHOICE:
        return normalize_choice_answer(user) == normalize_choice_answer(correct)

    # single_choice
    user_letter = user.upper()[0] if user else ""
    correct_letter = correct.upper()[0] if correct else ""
    return user_letter == correct_letter and user_letter in "ABCDEF"


def grade_question(question, user_answer: str) -> dict:
    """判分并返回结果"""
    is_correct = grade_answer(
        question.question_type,
        question.correct_answer,
        user_answer,
    )
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation or "",
    }
