import json
from crew_adapter import run_with_crew, crew_available


def pretty_print(res: dict):
    print(json.dumps(res, ensure_ascii=False, indent=2))


def main():
    print("=== Показати взаємодію агентів (verbose) ===")
    try:
        student = input("Введіть відповідь студента (Enter для прикладу): ")
    except EOFError:
        student = ""
    if not student:
        student = "Збір даних, навчання моделі і оцінка."

    correct = "Процес класифікації включає збір даних, вибір моделі, навчання, перевірку й оцінку метрик."

    res = run_with_crew(student, correct, course_id=None, topic="кроки класифікації")

    print('\n--- ORCHESTRATION ---')
    print(f"Crew available: {crew_available()}")
    print(f"Flow: {res.get('orchestration')}")

    print('\n--- GRADER AGENT RESULT ---')
    pretty_print(res.get('grader', {}))

    print('\n--- KNOWLEDGE CHECK RESULT ---')
    pretty_print(res.get('knowledge', {}))

    print('\n--- METHODOLGIST RESULT ---')
    pretty_print(res.get('methodologist', {}))

    print('\n--- PROMPT ENGINEER RESULT ---')
    pretty_print(res.get('prompt_engineer', {}))

    print('\n--- POLICY VALIDATION ---')
    pretty_print(res.get('policy_validation', {}))

    print('\n--- FEEDBACK AGENT RESULT ---')
    pretty_print(res.get('feedback', {}))


if __name__ == '__main__':
    main()
