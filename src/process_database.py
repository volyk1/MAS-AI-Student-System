import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_QUESTION_PATH = "data/question.json"
DEFAULT_OUTPUT_PATH = "data/current_session.json"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    return " ".join((text or "").casefold().replace("ё", "е").split())


def _detect_topic(question_text: str) -> str:
    q = _normalize(question_text)

    if any(k in q for k in ["implication", "de morgan's", "dnf", "karnaugh maps", "tautologies", "truth"]):
        return "Logic"
    if any(k in q for k in ["monoid", "subgroups", "Lagrange", "groups", "binary", "rings", "field"]):
        return "Algebraic structures"
    if any(k in q for k in ["sets", "subsets", "inclusion", "rational", "Cartesian", "symmetrical", "relationship"]):
        return "Set Theory"
    if any(k in q for k in ["matrices", "c = ab", "added", "multiplication", "reflection", "function"]):
        return "Functions and Matrices"
    if any(k in q for k in ["algorithm", "Gorner", "recursion", "big o", "binary"]):
        return "Algorithms and Recursion"
    if any(k in q for k in ["count", "peaks", "ribs", "Euler", "two-part", "incident", "trees"]):
        return "Graphs and Trees"

    return "Logic"


def _build_session(question_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    session = []

    for idx, item in enumerate(question_items):
        question_id = f"Q-{idx + 1:03d}"
        question_text = str(item.get("question", "")).strip()
        options = item.get("options", {}) if isinstance(item.get("options"), dict) else {}
        student_answer = str(item.get("student_answer", "")).strip()
        correct_answer = str(item.get("correct_answer", "")).strip()
        comment = str(item.get("comment", "")).strip()
        is_correct = student_answer == correct_answer
        provided_topic = str(item.get("topic", "")).strip()
        # Always prefer topic from question.json; detect only as fallback.
        stable_topic = provided_topic or _detect_topic(question_text)

        session.append(
            {
                "question_id": question_id,
                "question": question_text,
                "options": options,
                "correct_answer": correct_answer,
                "student_answer": student_answer,
                "is_correct": is_correct,
                "comment": comment,
                "topic": stable_topic,
            }
        )

    return session


def main(question_path: str = DEFAULT_QUESTION_PATH, output_path: str = DEFAULT_OUTPUT_PATH) -> None:
    source = _load_json(Path(question_path)) or {}
    questions = source.get("test", []) if isinstance(source, dict) else []

    if not isinstance(questions, list) or not questions:
        print(f"No questions found in: {question_path}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("[]", encoding="utf-8")
        return

    session = _build_session(questions)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(session)
    wrong = sum(1 for row in session if not row.get("is_correct", False))
    print(f"Generated current session: {total} questions, {wrong} mistakes.")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
