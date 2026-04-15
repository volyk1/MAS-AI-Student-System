const state = {
  session: [],
  analysisByQuestionId: new Map(),
  selectedQuestionId: null,
  currentPrompt: "",
  currentNotebookUrl: "",
};

const el = {
  totalCount: document.getElementById("totalCount"),
  correctCount: document.getElementById("correctCount"),
  wrongCount: document.getElementById("wrongCount"),
  refreshBtn: document.getElementById("refreshBtn"),
  questionList: document.getElementById("questionList"),
  detailHint: document.getElementById("detailHint"),
  detailQuestion: document.getElementById("detailQuestion"),
  detailTopic: document.getElementById("detailTopic"),
  detailStudent: document.getElementById("detailStudent"),
  detailCorrect: document.getElementById("detailCorrect"),
  detailExplanation: document.getElementById("detailExplanation"),
  detailContext: document.getElementById("detailContext"),
  detailPrompt: document.getElementById("detailPrompt"),
  errorSection: document.getElementById("errorSection"),
  explanationSection: document.getElementById("explanationSection"),
  promptSection: document.getElementById("promptSection"),
  copyBtn: document.getElementById("copyBtn"),
  openNotebookBtn: document.getElementById("openNotebookBtn"),
  copyOk: document.getElementById("copyOk"),
};

function clearDetails() {
  el.detailQuestion.textContent = "—";
  el.detailTopic.textContent = "—";
  el.detailStudent.textContent = "—";
  el.detailCorrect.textContent = "—";
  el.detailExplanation.textContent = "—";
  el.detailContext.textContent = "—";
  el.detailPrompt.textContent = "—";
  el.copyBtn.disabled = true;
  el.openNotebookBtn.disabled = true;
  el.errorSection.classList.remove("hidden");
  el.explanationSection.classList.remove("hidden");
  el.promptSection.classList.remove("hidden");
  state.currentPrompt = "";
  state.currentNotebookUrl = "";
}


function statusLabel(item) {
  return item.is_correct ? "Correct ✅" : "Error ❌";
}

function renderQuestionList() {
  el.questionList.innerHTML = "";

  state.session.forEach((item) => {
    const row = document.createElement("div");
    row.className = `question-row ${item.is_correct ? "ok" : "bad"}`;

    const top = document.createElement("div");
    top.className = "question-top";

    const qid = document.createElement("span");
    qid.className = "qid";
    qid.textContent = item.question_id;

    const badge = document.createElement("span");
    badge.className = `badge ${item.is_correct ? "ok" : "bad"}`;
    badge.textContent = statusLabel(item);

    top.appendChild(qid);
    top.appendChild(badge);

    const text = document.createElement("p");
    text.className = "question-text";
    text.textContent = item.question;

    const footer = document.createElement("div");
    footer.className = "question-footer";

    const topic = document.createElement("span");
    topic.className = "topic";
    topic.textContent = item.topic || "Без теми";

    footer.appendChild(topic);

    if (!item.is_correct) {
      const btn = document.createElement("button");
      btn.className = "mini-cta";
      btn.type = "button";
      btn.textContent = "AI Helper";
      btn.addEventListener("click", (evt) => {
        evt.stopPropagation();
        selectQuestion(item.question_id);
      });
      footer.appendChild(btn);
    }

    row.appendChild(top);
    row.appendChild(text);
    row.appendChild(footer);

    row.addEventListener("click", () => selectQuestion(item.question_id));
    el.questionList.appendChild(row);
  });
}

function updateStats(payload) {
  el.totalCount.textContent = String(payload.total_questions || 0);
  el.correctCount.textContent = String(payload.correct_count || 0);
  el.wrongCount.textContent = String(payload.wrong_count || 0);
}

async function loadSession() {
  const res = await fetch("/api/session");
  const payload = await res.json();

  state.session = payload.items || [];
  updateStats(payload);
  renderQuestionList();

  if (state.session.length > 0) {
    clearDetails();
    el.detailHint.textContent = "Select a test question to view the analysis and prompt.";
  }
}

function renderDetails(payload) {
  const selected = state.session.find((x) => x.question_id === payload.question_id);
  const isCorrect = Boolean(payload.is_correct);

  el.detailQuestion.textContent = payload.question || "—";
  el.detailTopic.textContent = payload.topic || "—";
  el.detailStudent.textContent = payload.student_answer || "—";
  el.detailCorrect.textContent = payload.correct_answer || "—";
  el.detailStudent.classList.remove("answer-wrong", "answer-ok");
  el.detailCorrect.classList.remove("answer-wrong", "answer-ok");
  el.detailContext.textContent = payload.context || "Context not available";

  if (isCorrect) {
    el.detailStudent.classList.add("answer-ok");
    el.detailCorrect.classList.add("answer-ok");
    el.detailHint.textContent = "Good job! That's right ✅";
    el.detailExplanation.textContent = payload.message || "Good job! That's right ✅";
    el.promptSection.classList.add("hidden");
    el.copyBtn.disabled = true;
    el.openNotebookBtn.disabled = true;
    state.currentPrompt = "";
    state.currentNotebookUrl = "";
    return;
  }

  el.detailStudent.classList.add("answer-wrong");
  el.detailCorrect.classList.add("answer-ok");
  el.promptSection.classList.remove("hidden");
  el.detailHint.textContent = "Error ❌. Personalized analysis available.";
  el.detailExplanation.textContent = payload.ai_explanation || "Explanation not available.";
  el.detailPrompt.textContent = payload.custom_prompt || "No prompt.";

  state.currentPrompt = payload.custom_prompt || "";
  state.currentNotebookUrl = payload.notebook_url || "";

  el.copyBtn.disabled = !state.currentPrompt.trim();
  el.openNotebookBtn.disabled = !state.currentNotebookUrl;

  if (selected) {
    const rows = document.querySelectorAll(".question-row");
    rows.forEach((row) => row.classList.remove("selected"));
    const target = Array.from(rows).find((row) => row.querySelector(".qid")?.textContent === selected.question_id);
    if (target) {
      target.classList.add("selected");
    }
  }
}

async function selectQuestion(questionId) {
  state.selectedQuestionId = questionId;
  const res = await fetch(`/api/analysis?question_id=${encodeURIComponent(questionId)}`);
  const payload = await res.json();
  renderDetails(payload);
}

async function refreshSession() {
  el.refreshBtn.disabled = true;
  try {
    await fetch("/api/rebuild");
    await loadSession();
    clearDetails();
    el.detailHint.textContent = "The session has been refreshed. Select a question from the list.";
  } finally {
    el.refreshBtn.disabled = false;
  }
}

async function copyPrompt() {
  const text = state.currentPrompt || "";
  if (!text.trim()) {
    return;
  }

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }

    el.copyOk.hidden = false;
    el.copyBtn.textContent = "Copied! ✅";
    setTimeout(() => {
      el.copyOk.hidden = true;
      el.copyBtn.textContent = "Copy the query";
    }, 1200);
  } catch (_err) {
    el.copyBtn.textContent = "Copy error";
    setTimeout(() => {
      el.copyBtn.textContent = "Copy the query";
    }, 1200);
  }
}

function openNotebook() {
  if (!state.currentNotebookUrl) {
    return;
  }
  window.open(state.currentNotebookUrl, "_blank", "noopener,noreferrer");
}

el.refreshBtn.addEventListener("click", refreshSession);
el.copyBtn.addEventListener("click", copyPrompt);
el.openNotebookBtn.addEventListener("click", openNotebook);

loadSession().catch(() => {
  el.detailHint.textContent = "Unable to load the session.";
});
