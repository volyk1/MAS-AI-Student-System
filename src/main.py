from agents import grader_agent, feedback_agent
import json
import argparse


def run_example(output_path: str = None):
    print("=== Приклад: перевірка відповіді студента ===")
    correct = (
        "Процес класифікації включає збір даних, вибір моделі, навчання, перевірку й оцінку метрик."
    )
    try:
        student = input("Введіть відповідь студента (або натисніть Enter для прикладу): ")
    except EOFError:
        student = ""
    if not student:
        student = "Збір даних, навчання моделі і оцінка."

    analysis = grader_agent(student, correct)
    feedback = feedback_agent(analysis, student, correct, topic="кроки класифікації")

    out = {"analysis": analysis, "feedback": feedback}
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"Збережено у файл: {output_path}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run grader/feedback example")
    parser.add_argument("--output", "-o", help="Path to output JSON file (UTF-8)")
    args = parser.parse_args()
    run_example(output_path=args.output)
