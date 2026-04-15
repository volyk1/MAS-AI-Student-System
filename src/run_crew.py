import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from agents import feedback_agent, grader_agent, policy_validator


DEFAULT_INPUT = "data/current_session.json"
DEFAULT_MAPPING = "data/notebook_mapping.json"
DEFAULT_OUTPUT = "data/final_analysis.json"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold().replace("ё", "е")).strip()


def _load_mapping(mapping_path: str = DEFAULT_MAPPING) -> Dict[str, Any]:
    data = _load_json(Path(mapping_path)) or {}
    return data if isinstance(data, dict) else {}


def _resolve_mapping(topic: str, question_text: str, mapping: Dict[str, Any]) -> Dict[str, Any]:
    topic_norm = _normalize(topic)
    question_norm = _normalize(question_text)

    best_topic = ""
    best_info: Dict[str, Any] = {}
    best_score = -1

    for mapped_topic, info in mapping.items():
        if not isinstance(info, dict):
            continue

        score = 0
        if _normalize(mapped_topic) == topic_norm and topic_norm:
            score += 6

        keywords = info.get("keywords", []) if isinstance(info.get("keywords"), list) else []
        for keyword in keywords:
            if _normalize(str(keyword)) in question_norm:
                score += 1

        if score > best_score:
            best_score = score
            best_topic = str(mapped_topic)
            best_info = info

    if not best_info and mapping:
        first_topic = next(iter(mapping.keys()))
        if isinstance(mapping[first_topic], dict):
            best_topic = str(first_topic)
            best_info = mapping[first_topic]

    return {
        "topic": best_topic or topic,
        "notebook_url": str(best_info.get("url") or best_info.get("notebooklm_workbook") or ""),
        "section": str(best_info.get("section") or ""),
        "keywords": best_info.get("keywords", []) if isinstance(best_info.get("keywords"), list) else [],
    }


def get_notebook_url(question_text: str, topic: str = "", mapping_path: str = DEFAULT_MAPPING) -> str:
    mapping = _load_mapping(mapping_path)
    return _resolve_mapping(topic, question_text, mapping).get("notebook_url", "")


def _build_architect_prompt(question_text: str, student_answer: str, correct_answer: str, comment: str = "") -> str:
    comment_block = f"Reason for the error (comment): {comment}\n" if comment else ""
    return (
        "Hi! I'm studying discrete mathematics using Anderson's textbook and want to figure out where I went wrong.\n\n"
        f"Question: {question_text}\n"
        f"My answer: {student_answer}\n"
        f"The correct answer: {correct_answer}\n"
        f"{comment_block}\n"
        "Please explain in simple terms where I went wrong and how to think correctly."
        "Then provide 2 short self-assessment questions and 3 exercises: easy, medium, and difficult."
    )


def _analyze_wrong_answer(row: Dict[str, Any], mapping: Dict[str, Any]) -> Dict[str, Any]:
    question_id = row.get("question_id", "")
    question_text = row.get("question", "")
    student_answer = row.get("student_answer", "")
    correct_answer = row.get("correct_answer", "")
    options = row.get("options", {}) if isinstance(row.get("options"), dict) else {}

    # Use answer texts for agent tasks; fallback safely to raw values when key is missing.
    student_answer_text = str(options.get(student_answer, student_answer))
    correct_answer_text = str(options.get(correct_answer, correct_answer))

    comment = row.get("comment", "")
    topic = row.get("topic", "")

    mapping_info = _resolve_mapping(topic, question_text, mapping)
    notebook_url = mapping_info.get("notebook_url", "")

    grader = grader_agent(student_answer_text, correct_answer_text)
    feedback = feedback_agent(grader, student_answer_text, correct_answer_text, topic=mapping_info.get("topic", topic))

    analyst_text = (
        "Analyst: "
        f"error in the subject line '{mapping_info.get('topic', topic)}'. "
        f"The student chose '{student_answer_text}', whereas the correct answer is: '{correct_answer_text}'. "
        f"{('Comment on the error: ' + str(comment) + '. ') if comment else ''}"
        "It is recommended that you review the definition and complete a short exercise using a similar example."
    )

    architect_prompt = _build_architect_prompt(
        question_text=question_text,
        student_answer=student_answer_text,
        correct_answer=correct_answer_text,
        comment=comment,
    )

    validation = policy_validator(architect_prompt)

    return {
        "question_id": question_id,
        "question": question_text,
        "topic": mapping_info.get("topic", topic),
        "student_answer": student_answer,
        "correct_answer": correct_answer,
        "student_answer_text": student_answer_text,
        "correct_answer_text": correct_answer_text,
        "comment": comment,
        "is_correct": False,
        "analyst": {
            "role": "Analyst",
            "language": "uk",
            "ai_explanation": analyst_text,
        },
        "architect": {
            "role": "Architect",
            "language": "uk",
            "custom_prompt": architect_prompt,
        },
        "routing": {
            "notebook_url": notebook_url,
            "section": mapping_info.get("section", ""),
            "keywords": mapping_info.get("keywords", []),
        },
        "grader": grader,
        "feedback": feedback,
        "policy_validation": validation,
    }


def main(input_path: str = DEFAULT_INPUT, output_path: str = DEFAULT_OUTPUT, mapping_path: str = DEFAULT_MAPPING) -> None:
    rows = _load_json(Path(input_path)) or []
    if not isinstance(rows, list):
        raise ValueError("Input must be a JSON array")

    mapping = _load_mapping(mapping_path)

    wrong_rows = [row for row in rows if isinstance(row, dict) and not row.get("is_correct", False)]
    analysis = [_analyze_wrong_answer(row, mapping) for row in wrong_rows]

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Processed session questions: {len(rows)}")
    print(f"Analyzed mistakes only: {len(analysis)}")
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to current_session JSON")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to final analysis JSON")
    parser.add_argument("--mapping", default=DEFAULT_MAPPING, help="Path to notebook mapping JSON")
    args = parser.parse_args()
    main(input_path=args.input, output_path=args.output, mapping_path=args.mapping)
