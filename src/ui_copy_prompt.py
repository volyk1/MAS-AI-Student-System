"""Static frontend server for MAS AI Student System.

Single run command:
python src/ui_copy_prompt.py --port 8000
"""
import argparse
import json
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from process_database import main as process_database_main
from run_crew import main as run_crew_main


BASE_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = BASE_DIR / "frontend"
SESSION_PATH = BASE_DIR / "data" / "current_session.json"
ANALYSIS_PATH = BASE_DIR / "data" / "final_analysis.json"
KEEP_JSON_FILES = {"question.json", "notebook_mapping.json", "current_session.json", "final_analysis.json"}


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _cleanup_legacy_results() -> None:
    data_dir = BASE_DIR / "data"
    if not data_dir.exists():
        return

    for p in data_dir.iterdir():
        if not p.is_file() or p.suffix.lower() != ".json":
            continue
        if p.name in KEEP_JSON_FILES:
            continue
        p.unlink()


def _ensure_pipeline() -> None:
    _cleanup_legacy_results()
    print("[AUTO] Session generation: question.json -> current_session.json -> final_analysis.json")
    process_database_main(
        question_path="data/question.json",
        output_path="data/current_session.json",
    )
    run_crew_main(
        input_path="data/current_session.json",
        output_path="data/final_analysis.json",
        mapping_path="data/notebook_mapping.json",
    )


def _load_session_and_analysis():
    session_rows = _load_json(SESSION_PATH)
    analysis_rows = _load_json(ANALYSIS_PATH)

    if not isinstance(session_rows, list):
        session_rows = []
    if not isinstance(analysis_rows, list):
        analysis_rows = []

    analysis_by_id = {}
    for row in analysis_rows:
        if not isinstance(row, dict):
            continue
        qid = row.get("question_id")
        if qid:
            analysis_by_id[qid] = row

    return session_rows, analysis_rows, analysis_by_id


def _build_session_payload():
    session_rows, _, analysis_by_id = _load_session_and_analysis()
    items = []

    correct_count = 0
    wrong_count = 0

    for idx, row in enumerate(session_rows):
        if not isinstance(row, dict):
            continue

        qid = row.get("question_id", f"Q-{idx + 1:03d}")
        is_correct = bool(row.get("is_correct", False))
        if is_correct:
            correct_count += 1
        else:
            wrong_count += 1

        items.append(
            {
                "index": idx,
                "question_id": qid,
                "question": row.get("question", ""),
                "topic": row.get("topic", ""),
                "is_correct": is_correct,
                "student_answer": row.get("student_answer", ""),
                "correct_answer": row.get("correct_answer", ""),
                "has_help": qid in analysis_by_id,
            }
        )

    return {
        "ok": True,
        "total_questions": len(items),
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "items": items,
    }


def _build_analysis_payload(question_id: str):
    session_rows, _, analysis_by_id = _load_session_and_analysis()

    session_row = None
    for row in session_rows:
        if isinstance(row, dict) and row.get("question_id") == question_id:
            session_row = row
            break

    if not session_row:
        return {
            "ok": False,
            "question_id": question_id,
            "message": "No results found for this query in the current session.",
        }

    is_correct = bool(session_row.get("is_correct", False))
    analysis = analysis_by_id.get(question_id, {}) if isinstance(analysis_by_id.get(question_id), dict) else {}
    options = session_row.get("options", {}) if isinstance(session_row.get("options"), dict) else {}

    student_answer_raw = session_row.get("student_answer", "")
    correct_answer_raw = session_row.get("correct_answer", "")

    student_answer_text = (
        analysis.get("student_answer_text")
        or options.get(student_answer_raw, student_answer_raw)
    )
    correct_answer_text = (
        analysis.get("correct_answer_text")
        or options.get(correct_answer_raw, correct_answer_raw)
    )

    prompt_text = analysis.get("architect", {}).get("custom_prompt", "")
    notebook_url = analysis.get("routing", {}).get("notebook_url", "")
    ai_explanation = analysis.get("analyst", {}).get("ai_explanation", "")
    context = ""

    routing = analysis.get("routing", {}) if isinstance(analysis.get("routing"), dict) else {}
    topic = analysis.get("topic") or session_row.get("topic", "")
    section = routing.get("section", "")
    keywords = routing.get("keywords", []) if isinstance(routing.get("keywords"), list) else []
    if topic:
        context = f"Topic: {topic}"
    if section:
        context = f"{context} | Section: {section}" if context else f"Section: {section}"
    if keywords:
        context = f"{context} | Keywords: {', '.join(keywords[:6])}" if context else f"Keywords: {', '.join(keywords[:6])}"

    return {
        "ok": True,
        "question_id": question_id,
        "question": session_row.get("question", ""),
        "options": session_row.get("options", {}),
        "topic": topic,
        "is_correct": is_correct,
        "student_answer": student_answer_text,
        "correct_answer": correct_answer_text,
        "student_answer_raw": student_answer_raw,
        "correct_answer_raw": correct_answer_raw,
        "ai_explanation": ai_explanation,
        "custom_prompt": prompt_text,
        "notebook_url": notebook_url,
        "context": context,
        "has_help": not is_correct and bool(prompt_text),
        "message": "The answer is correct. No additional AI assistance is needed." if is_correct else "",
    }


class PromptHandler(BaseHTTPRequestHandler):
    def _write_json(self, obj, status=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_file(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "Not found")
            return

        mime, _ = mimetypes.guess_type(str(file_path))
        content_type = mime or "application/octet-stream"
        body = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/api/session":
            self._write_json(_build_session_payload())
            return

        if parsed.path == "/api/analysis":
            qid = qs.get("question_id", [""])[0]
            self._write_json(_build_analysis_payload(qid))
            return

        if parsed.path == "/api/rebuild":
            _ensure_pipeline()
            self._write_json({"ok": True, "message": "Session updated."})
            return

        route = parsed.path
        if route in ("", "/"):
            self._serve_file(FRONTEND_DIR / "index.html")
            return

        clean_route = route.lstrip("/")
        self._serve_file(FRONTEND_DIR / clean_route)


def run_server(port: int = 8000):
    _ensure_pipeline()

    server = HTTPServer(("localhost", port), PromptHandler)
    print(f"Serving frontend UI at http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down server")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-file", default="data/final_analysis.json", help="Legacy flag; ignored by new flow")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--record", type=int, default=0, help="Legacy flag; ignored by new flow")
    args = parser.parse_args()
    run_server(port=args.port)
