from typing import Any, Dict, List
import difflib
from typing import Optional
import json
import re
from pathlib import Path


def grader_agent(student_answer: str, correct_answer: str) -> Dict[str, Any]:
	"""Агент-оцінювач: порівнює відповідь студента з правильною відповіддю.

	Повертає словник з полями:
	- correct: bool
	- score: float (0..1)
	- diff: list[str] (лінії diff з difflib.ndiff)
	- summary: короткий текстовий висновок
	"""
	sa = (student_answer or "").strip()
	ca = (correct_answer or "").strip()

	# Простий коефіцієнт схожості
	matcher = difflib.SequenceMatcher(None, sa, ca)
	score = matcher.ratio()

	# Груба логіка правильності
	correct = False
	if sa == ca or score >= 0.95:
		correct = True

	# Генеруємо лінійний diff для читабельності
	diff_lines = list(difflib.ndiff([sa], [ca])) if sa and ca else []

	# Короткий текстовий висновок
	if correct:
		summary = "Відповідь вважається правильною або без значущих відхилень."
	elif score >= 0.6:
		summary = "Відповідь частково вірна — є пропуски або деталі."
	else:
		summary = "Відповідь помилкова — спостерігається невірне розуміння або пропуск ключових моментів."

	return {
		"correct": correct,
		"score": round(score, 3),
		"diff": diff_lines,
		"summary": summary,
	}


def _extract_topic_from_text(text: str) -> str:
	keywords = {
		"класифікац": "кроки класифікації",
		"регрес": "регресія",
		"нейрон": "нейронні мережі",
		"нормал": "передобробка / нормалізація",
		"метрик": "оцінка та метрики",
		"стек": "Лінійні структури даних",
		"binary": "Складність алгоритмів",
		"log n": "Складність алгоритмів",
	}
	tl = (text or "").lower()
	for k, t in keywords.items():
		if k in tl:
			return t
	if "classification" in tl:
		return "кроки класифікації"
	return "загальні питання курсу"


def _concept_description(topic: str) -> str:
	concepts = {
		"кроки класифікації": "Послідовність етапів класифікації: підготовка даних, вибір моделі, навчання, валідація та оцінка метрик.",
		"Лінійні структури даних": "Принципи роботи лінійних структур, зокрема різниця між LIFO (stack) і FIFO (queue).",
		"Складність алгоритмів": "Асимптотична складність: як оцінити швидкість алгоритму залежно від розміру вхідних даних.",
	}
	return concepts.get(topic, f"Ключові поняття теми: {topic}.")


def normalize_topic(topic: str) -> str:
	"""Normalizes a topic label for resilient cross-file matching.

	Examples:
	- "AI_Ethics" -> "ai ethics"
	- "AI Ethics" -> "ai ethics"
	- "Кроки   класифікації" -> "кроки класифікації"
	"""
	text = (topic or "").strip().casefold()
	text = text.replace("_", " ").replace("-", " ")
	text = re.sub(r"\s+", " ", text)
	return text


def knowledge_check_agent(test_input: Any) -> Dict[str, Any]:
	"""Агент аналізу помилок.

	Підтримує 2 режими входу:
	1) Рядок test_log (backward-compatible).
	2) Структурований словник (рекомендовано), зокрема запис із current_session/question.

	Повертає topic, evidence, question_id, error_text, concept_description.
	"""
	if isinstance(test_input, dict):
		rec = test_input
		meta = rec.get("record_meta", {}) if isinstance(rec.get("record_meta"), dict) else {}
		source = rec.get("source_record", {}) if isinstance(rec.get("source_record"), dict) else {}
		grader = rec.get("grader", {}) if isinstance(rec.get("grader"), dict) else {}

		question_id = rec.get("question_id") or source.get("question_id") or meta.get("question_id")
		if not question_id:
			course = meta.get("course_id") or source.get("course_id") or "GEN"
			title = meta.get("test_title") or source.get("test_title") or "question"
			question_id = f"{course}:{str(title).replace(' ', '_')}"

		question_text = rec.get("question_text") or source.get("question_text") or ""
		student_answer = rec.get("student_answer") or source.get("student_answer") or ""
		correct_answer = rec.get("correct_answer") or source.get("correct_answer") or ""

		topic = rec.get("topic") or source.get("topic") or rec.get("knowledge_check", {}).get("topic")
		if not topic:
			topic = _extract_topic_from_text(f"{question_text}\n{student_answer}\n{correct_answer}")

		diff_preview = "\n".join(grader.get("diff", [])[:4]) if grader else ""
		error_text = rec.get("error_text")
		if not error_text:
			summary = grader.get("summary", "")
			error_text = (
				f"Питання: {question_text}\n"
				f"Помилка студента: {summary or 'відповідь не збігається з еталоном'}\n"
				f"Відповідь студента: {student_answer}\n"
				f"Очікувана відповідь: {correct_answer}"
			)
			if diff_preview:
				error_text += f"\nDiff:\n{diff_preview}"

		evidence = [
			f"question_id: {question_id}",
			f"question: {question_text}",
			f"topic: {topic}",
		]

		return {
			"question_id": question_id,
			"topic": topic,
			"error_text": error_text,
			"concept_description": _concept_description(topic),
			"evidence": evidence,
		}

	tl = (test_input or "").lower()
	if not tl:
		tl = "student answered: 'збір даних, навчання моделі і оцінка' for question about classification"

	topic = _extract_topic_from_text(tl)
	evidence = [line.strip() for line in tl.splitlines() if line.strip()][:4]
	if not evidence:
		evidence = [tl[:200]]

	return {
		"question_id": None,
		"topic": topic,
		"error_text": tl[:300],
		"concept_description": _concept_description(topic),
		"evidence": evidence,
	}


def methodologist_agent(topic: str, course_id: Optional[str] = None) -> Dict[str, Any]:
	"""Підбирає матеріали виключно через data/notebook_mapping.json.

	Workbook URL має відповідати визначеній темі з notebook_mapping.json.
	"""
	mapping_path = Path("data/notebook_mapping.json")
	mapping = {}
	if mapping_path.exists():
		try:
			mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
		except Exception:
			mapping = {}

	info = None
	matched_topic_key = topic
	norm_topic = normalize_topic(topic)

	def find_by_normalized_key(m: Dict[str, Any], wanted_norm: str):
		for k, v in m.items():
			if normalize_topic(k) == wanted_norm:
				return k, v
		return None, None

	# course-specific override
	if course_id and mapping.get(course_id) and isinstance(mapping[course_id], dict):
		course_map = mapping[course_id]
		if topic in course_map:
			info = course_map[topic]
		else:
			k, v = find_by_normalized_key(course_map, norm_topic)
			if v is not None:
				matched_topic_key = k
				info = v

	if not info:
		if topic in mapping:
			info = mapping.get(topic)
		else:
			k, v = find_by_normalized_key(mapping, norm_topic) if isinstance(mapping, dict) else (None, None)
			if v is not None:
				matched_topic_key = k
				info = v

	fallback_used = False
	if not info:
		# Context-check: do not invent workbook links when topic is missing in mapping.
		# Provide a safe fallback to an Obsidian note and a general textbook link.
		fallback_used = True
		info = {
			"section": f"Матеріали з теми: {topic}",
			"obsidian": f"obsidian://open?vault=course&file={topic.replace(' ', '%20')}",
			"notebooklm_workbook": "",
			"general_textbook": "https://example.com/general-textbook",
			"source_file": "",
			"source_section": "",
		}

	return {
		"topic": topic,
		"matched_topic": matched_topic_key,
		"normalized_topic": norm_topic,
		"section": info.get("section"),
		"obsidian_link": info.get("obsidian"),
		"workbook_link": info.get("notebooklm_workbook"),
		"general_textbook_link": info.get("general_textbook", ""),
		"source_file": info.get("source_file", ""),
		"source_section": info.get("source_section", ""),
		"fallback_used": fallback_used,
		"fallback_message": "Topic not found in mapping; using Obsidian/general textbook fallback." if fallback_used else "",
		"mapping_source": str(mapping_path),
	}


def prompt_engineer_agent(
	student_answer: str,
	correct_answer: str,
	topic: str,
	evidence: List[str],
	student_context: Optional[Dict[str, Any]] = None,
	concept_description: str = "",
	workbook_link: str = "",
	section: str = "",
	question_id: Optional[str] = None,
	error_text: str = "",
	topic_fail_count: int = 1,
	source_file: str = "",
	source_section: str = "",
	obsidian_link: str = "",
	question_text: str = "",
) -> Dict[str, Any]:
	"""Формує запит від першої особи студента без вставки URL у текст prompt.

	Повертає `notebooklm_query`, `student_instruction`, `action` та поля для UI.
	"""
	context_lines = []
	if student_context:
		if student_context.get("level"):
			context_lines.append(f"Рівень студента: {student_context['level']}")
		if student_context.get("prior_topics"):
			context_lines.append(f"Попередні теми: {', '.join(student_context['prior_topics'])}")

	context_text = "\n".join(context_lines)

	if not concept_description:
		concept_description = _concept_description(topic)

	memory_note = ""
	if topic_fail_count >= 3:
		memory_note = (
			f"Це вже {topic_fail_count}-тя помилка в темі '{topic}'. "
			"Зверни особливу увагу на базові визначення, типові пастки і перевір себе на прикладі."
		)

	if workbook_link and source_file:
		action = (
			"Скопіюй готовий prompt нижче у NotebookLM workbook і запусти. "
			f"Фокус: файл {source_file}" + (f", розділ {source_section}." if source_section else ".")
		)
	elif workbook_link:
		action = "Скопіюй готовий prompt нижче у NotebookLM workbook і запусти."
	else:
		action = (
			"Воркбук для цієї теми не знайдено. Використай Obsidian-замітку/загальний підручник "
			"і попроси AI пояснити термін простими словами та дати 3 міні-вправи."
		)

	comment_line = f"Додатковий коментар до моєї помилки: {error_text}" if error_text else ""
	memory_line = f"У цій темі я вже помиляюся не вперше: {memory_note}" if memory_note else ""
	evidence_line = ""
	if evidence:
		evidence_line = "Що я занотував: " + "; ".join([str(x) for x in evidence[:3]])

	full_query = (
		f"Привіт! Я вивчаю тему {topic} за Андерсоном. "
		f"У тесті на питання '{question_text or 'без назви питання'}' я відповів '{student_answer}', "
		f"але правильна відповідь — '{correct_answer}'. "
		"Допоможи мені зрозуміти, чому моя відповідь помилкова і в чому полягає логіка правильного варіанту.\n\n"
		f"Що саме не розумію: {concept_description}.\n"
		f"{comment_line}\n"
		f"{memory_line}\n"
		f"{evidence_line}\n\n"
		"Поясни простими словами, дай короткий покроковий розбір, "
		"постав 2 уточнювальні запитання і запропонуй 3 міні-вправи (легка, середня, складна)."
	).strip()

	student_instruction = f"Скопіюйте цей запит у NotebookLM workbook ({workbook_link or 'посилання відсутнє'}) та запустіть його для теми '{topic}'."

	return {
		"notebooklm_query": full_query,
		"student_instruction": student_instruction,
		"action": action,
		"memory_note": memory_note,
		"topic_fail_count": topic_fail_count,
		"concept_description": concept_description,
		"workbook_link": workbook_link,
		"source_file": source_file,
		"source_section": source_section,
		"question_id": question_id,
		"ui_preview": {
			"title": f"Розбір помилки: {topic}",
			"workbook_link": workbook_link,
			"action": action,
		},
	}


def policy_validator(prompt: str, policy_text: str = None) -> Dict[str, Any]:
	"""Перевіряє згенерований prompt на відповідність загальній політиці університету.

	Простий лінійний валідатор, що шукає заборонені ключові слова/патерни та повертає перелік проблем.
	"""
	issues = []
	p = (prompt or "").lower()

	forbidden_phrases = [
		"bypass", "cheat", "explain exam answers", "generate answers for exam", "personal data",
		"student id", "ssn", "passport", "credit card",
	]

	for phrase in forbidden_phrases:
		if phrase in p:
			issues.append(f"Contains forbidden phrase: '{phrase}'")

	if "personal data" in p or "student id" in p:
		issues.append("Requests PII — not allowed by policy")

	# Optional semantic check via OpenAI if available
	llm_result = None
	try:
		import os
		if os.environ.get("OPENAI_API_KEY"):
			try:
				import importlib
				openai = importlib.import_module("openai")
				openai.api_key = os.environ.get("OPENAI_API_KEY")
				# Compose a short prompt to check policy compliance
				system = "You are an assistant that checks whether a user prompt violates the provided AI policy. Respond with JSON: {\"ok\": bool, \"issues\": [str,...]}"
				user = f"Policy:\n{policy_text or ''}\n\nPrompt:\n{prompt}\n\nList any policy violations or answer ok:true if none."
				resp = openai.ChatCompletion.create(
					model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini") if os.environ.get("OPENAI_MODEL") else "gpt-4o-mini",
					messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
					max_tokens=200,
					temperature=0,
				)
				txt = resp.choices[0].message.content
				# Try to parse JSON from response
				import re
				m = re.search(r"\{.*\}", txt, re.S)
				if m:
					import json as _json
					parsed = _json.loads(m.group(0))
					llm_result = parsed
			except Exception:
				llm_result = None
	except Exception:
		llm_result = None

	if llm_result:
		# merge LLM findings with keyword issues
		combined_issues = list(set(issues + llm_result.get("issues", [])))
		ok = llm_result.get("ok", len(combined_issues) == 0)
		return {"ok": ok, "issues": combined_issues, "llm_checked": True}

	ok = len(issues) == 0
	return {"ok": ok, "issues": issues, "llm_checked": False}


def _guess_error_type(student_answer: str, correct_answer: str, score: float) -> str:
	sa = (student_answer or "").strip()
	ca = (correct_answer or "").strip()
	if not sa:
		return "відсутня відповідь"
	if score >= 0.6:
		return "часткова вірність або недостатня деталізація"
	if len(sa) < len(ca) * 0.5:
		return "недостатня деталізація"
	return "невірне розуміння ключових понять"


def feedback_agent(analysis: Dict[str, Any], student_answer: str, correct_answer: str, topic: str = None) -> Dict[str, Any]:
	"""Агент зворотного зв'язку: на основі аналізу дає пояснення, рекомендації, посилання, і генерує промпт для NotebookLM.

	Повертає:
	- explanation: детальний текст пояснення помилки
	- recommendations: список коротких порад
	- links: список рекомендованих ресурсів (title, url)
	- notebooklm_prompt: готовий запит для NotebookLM
	"""
	score = analysis.get("score", 0)
	correct = analysis.get("correct", False)

	if correct:
		explanation = "Відповідь правильна. Рекомендацій очевидно небагато: повторіть матеріал для закріплення."
		recommendations = ["Переглянути приклади; попрактикуватися в подібних завданнях."]
	else:
		error_type = _guess_error_type(student_answer, correct_answer, score)
		explanation = (
			f"Аналіз показує: {analysis.get('summary')}\n"
			f"Імовірний тип помилки: {error_type}.\n"
			"Детально: порівняння відповіді студента і правильної відповіді (diff) нижче."
		)
		# Додаємо частину diff для наочності
		diff_preview = "\n".join(analysis.get("diff", [])[:10])
		if diff_preview:
			explanation += "\nDiff:\n" + diff_preview

		recommendations = [
			"Уточнити визначення ключових термінів у питанні.",
			"Розбити задачу на кроки і перевірити проміжні висновки.",
			"Відпрацювати приклади з практичними вправами за темою."
		]

	# Приклади посилань — в реальному проєкті ці URL можна брати з бази знань
	links = []
	if topic:
		links.append({"title": f"Оглядова стаття по темі: {topic}", "url": f"https://example.com/materials/{topic.replace(' ', '%20')}"})
	# Рекомендований ресурс: NotebookLM (запитальник)
	links.append({"title": "NotebookLM (запустіть цей запит)", "url": "https://workspace.google.com/notebook-lm"})

	# Генеруємо промпт для NotebookLM — студентський варіант, щоб NotebookLM пояснив помилку та дав план навчання
	notebooklm_prompt = (
		"You are a helpful tutor. A student submitted the following answer and it was evaluated against the correct answer.\n"
		"Provide a clear, step-by-step explanation of where the student went wrong, a concise conceptual correction, and a short practice plan (3 exercises) with increasing difficulty.\n\n"
		f"Correct answer:\n{correct_answer}\n\n"
		f"Student answer:\n{student_answer}\n\n"
		"Also include suggested external readings or resources and recommend how the student should use them (e.g., which sections to read, what to practice)."
	)

	return {
		"explanation": explanation,
		"recommendations": recommendations,
		"links": links,
		"notebooklm_prompt": notebooklm_prompt,
	}


if __name__ == "__main__":
	# Простий приклад локального запуску
	import json
	sa = input("Введіть відповідь студента: ")
	ca = input("Введіть правильну відповідь: ")
	analysis = grader_agent(sa, ca)
	feedback = feedback_agent(analysis, sa, ca, topic=None)
	out = {"analysis": analysis, "feedback": feedback}
	print(json.dumps(out, ensure_ascii=False, indent=2))

