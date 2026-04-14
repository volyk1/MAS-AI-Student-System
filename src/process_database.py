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

    if any(k in q for k in ["імплікац", "де морган", "днф", "карно", "тавтолог", "істинност"]):
        return "Логіка"
    if any(k in q for k in ["моноїд", "напівгруп", "підгруп", "лагранж", "груп", "бінарн", "кільц", "поле"]):
        return "Алгебраїчні структури"
    if any(k in q for k in ["множин", "підмножин", "включенн", "раціональ", "декартов", "симетричн", "відношенн"]):
        return "Теорія множин"
    if any(k in q for k in ["матриц", "c = ab", "додаван", "множенн", "відображенн", "функц"]):
        return "Функції та матриці"
    if any(k in q for k in ["алгоритм", "горнер", "рекурс", "big o", "бінарн"]):
        return "Алгоритми та рекурсія"
    if any(k in q for k in ["граф", "вершин", "ребер", "ейлер", "двочастков", "інцидент", "дерев"]):
        return "Графи та дерева"

    return "Логіка"


def _build_session(question_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    session = []

    for idx, item in enumerate(question_items):
        question_text = str(item.get("question", "")).strip()
        options = item.get("options", {}) if isinstance(item.get("options"), dict) else {}
        student_answer = str(item.get("student_answer", "")).strip()
        correct_answer = str(item.get("correct_answer", "")).strip()
        comment = str(item.get("comment", "")).strip()
        is_correct = student_answer == correct_answer

        session.append(
            {
                "question_id": f"Q-{idx + 1:03d}",
                "question": question_text,
                "options": options,
                "correct_answer": correct_answer,
                "student_answer": student_answer,
                "is_correct": is_correct,
                "comment": comment,
                "topic": _detect_topic(question_text),
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
