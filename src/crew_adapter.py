"""Адаптер для інтеграції з CrewAI або локальна емулляція оркестрації агентів.

Цей модуль намагається імпортувати пакет `crewai`. Якщо він доступний,
можна реалізувати реальний реєстраційний код тут. Якщо пакета немає,
функція `run_with_crew_emulation` послідовно викликає `grader_agent`
та `feedback_agent`, і повертає об'єднаний результат — це дозволяє тестувати
логіку без зовнішніх залежностей.
"""
from pathlib import Path
from typing import Dict, Any

try:
    import crewai  # type: ignore
    CREW_AVAILABLE = True
except Exception:
    crewai = None  # type: ignore
    CREW_AVAILABLE = False

from agents import grader_agent, knowledge_check_agent, methodologist_agent, prompt_engineer_agent, policy_validator, feedback_agent


def run_with_crew_emulation(student_answer: str, correct_answer: str, course_id: str = None, topic: str = None) -> Dict[str, Any]:
    """Емулює оркестрацію CrewAI: KnowledgeCheck -> Methodologist -> PromptEngineer, включаючи grader та policy validation.

    Повертає словник з полями: grader, knowledge, methodologist, prompt_engineer, policy_validation, feedback, orchestration
    """
    grader_res = grader_agent(student_answer, correct_answer)

    knowledge_res = knowledge_check_agent(
        {
            "question_id": None,
            "question_text": f"Question topic hint: {topic or ''}",
            "student_answer": student_answer,
            "correct_answer": correct_answer,
            "topic": topic,
            "grader": grader_res,
            "record_meta": {"course_id": course_id},
        }
    )

    method_res = methodologist_agent(knowledge_res.get("topic"), course_id)

    prompt_res = prompt_engineer_agent(
        student_answer=student_answer,
        correct_answer=correct_answer,
        topic=knowledge_res.get("topic"),
        evidence=knowledge_res.get("evidence", []),
        student_context={},
        concept_description=knowledge_res.get("concept_description", ""),
        workbook_link=method_res.get("workbook_link", ""),
        section=method_res.get("section", ""),
        question_id=knowledge_res.get("question_id"),
        error_text=knowledge_res.get("error_text", ""),
    )

    # Validate prompt against policy
    policy_text = None
    try:
        p = Path("data/ai_policy.txt")
        if p.exists():
            policy_text = p.read_text(encoding="utf-8")
    except Exception:
        policy_text = None

    validation = policy_validator(prompt_res.get("notebooklm_query", ""), policy_text=policy_text)

    feedback_res = feedback_agent(grader_res, student_answer, correct_answer, topic=knowledge_res.get("topic"))

    return {
        "grader": grader_res,
        "knowledge": knowledge_res,
        "methodologist": method_res,
        "prompt_engineer": prompt_res,
        "policy_validation": validation,
        "feedback": feedback_res,
        "orchestration": "emulated: knowledge -> methodologist -> prompt_engineer",
    }


def crew_available() -> bool:
    return CREW_AVAILABLE


def run_with_crew(student_answer: str, correct_answer: str, course_id: str = None, topic: str = None) -> Dict[str, Any]:
    """Якщо `crewai` доступний, тут можна реалізувати реальний запуск через CrewAI API.

    Наразі, якщо `crewai` недоступний, викликає емульовану версію.
    """
    if not CREW_AVAILABLE:
        return run_with_crew_emulation(student_answer, correct_answer, course_id=course_id, topic=topic)

    # Placeholder: приклад структури для реальної інтеграції
    # Реальна реалізація залежатиме від API CrewAI; тут повертаємо емулюваний результат.
    return run_with_crew_emulation(student_answer, correct_answer, course_id=course_id, topic=topic)
