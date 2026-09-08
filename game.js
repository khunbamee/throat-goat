const QUESTIONS_PER_DIVE = 7;
const SECONDS_PER_QUESTION = 25;
const SCORE_LABELS = new Map([[10, "Common"], [20, "Familiar"], [40, "Uncommon"], [60, "Rare"], [80, "Deep Cut"], [100, "Abyssal"]]);

const state = {
  bank: [], dive: [], index: 0, answers: [], answerMap: new Map(),
  score: 0, timer: null, seconds: SECONDS_PER_QUESTION,
  answered: false, mode: "daily", results: []
};

const $ = (id) => document.getElementById(id);

function normalizeAnswer(text) {
  return String(text ?? "")
    .toLowerCase().trim().normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’']/g, "")
    .replace(/&/g, " and ")
    .replace(/[-–—:;/,.!?()[\]{}]+/g, " ")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/^(the|a|an)\s+/, "")
    .replace(/\s+/g, " ").trim();
}

function buildAnswerMap(answers) {
  const map = new Map();
  for (const answer of answers) {
    for (const value of [answer.name, ...(answer.aliases || [])]) {
      const key = normalizeAnswer(value);
      if (key && !map.has(key)) map.set(key, answer);
    }
  }
  return map;
}

function hashString(input) {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed) {
  return function () {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffledCopy(array, random = Math.random) {
  const copy = [...array];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function utcDateKey() { return new Date().toISOString().slice(0, 10); }

function chooseDiverseQuestions(bank, count, random) {
  const byCategory = new Map();
  for (const q of shuffledCopy(bank, random)) {
    const category = q.category || "general";
    if (!byCategory.has(category)) byCategory.set(category, []);
    byCategory.get(category).push(q);
  }
  const categories = shuffledCopy([...byCategory.keys()], random);
  const chosen = [];
  while (chosen.length < count) {
    let added = false;
    for (const category of categories) {
      const list = byCategory.get(category);
      if (list && list.length) {
        chosen.push(list.shift());
        added = true;
        if (chosen.length === count) break;
      }
    }
    if (!added) break;
  }
  return chosen;
}

function dailySelection() {
  const random = mulberry32(hashString(`deep-answer:${utcDateKey()}`));
  return chooseDiverseQuestions(state.bank, Math.min(QUESTIONS_PER_DIVE, state.bank.length), random);
}

function practiceSelection() {
  return chooseDiverseQuestions(state.bank, Math.min(QUESTIONS_PER_DIVE, state.bank.length), Math.random);
}

async function loadBank() {
  try {
    const response = await fetch("data/questions.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Question bank HTTP ${response.status}`);
    const data = await response.json();
    if (!Array.isArray(data) || !data.length) throw new Error("Question bank is empty");
    state.bank = data;
    $("bank-status").textContent = `${data.length.toLocaleString()} questions ready`;
    $("daily-button").disabled = false;
    $("practice-button").disabled = false;
    updateDailyNote();
  } catch (error) {
    console.error(error);
    $("bank-status").textContent = "Could not load the question bank. Try refreshing.";
  }
}

function updateDailyNote() {
  const saved = localStorage.getItem(`deep-answer-daily:${utcDateKey()}`);
  $("daily-note").textContent = saved
    ? `Today's Daily Dive completed — ${saved} points. You can still replay it.`
    : "Daily Dive uses the same question set for everyone each UTC day.";
}

async function loadAnswers(question) {
  if (Array.isArray(question.answers)) return question.answers;
  const path = question.answer_file || `data/answers/${question.id}.json`;
  const response = await fetch(path, { cache: "force-cache" });
  if (!response.ok) throw new Error(`Answers HTTP ${response.status} for ${question.id}`);
  const data = await response.json();
  return Array.isArray(data) ? data : (data.answers || []);
}

function showScreen(name) {
  $("start-screen").hidden = name !== "start";
  $("game-screen").hidden = name !== "game";
  $("end-screen").hidden = name !== "end";
}

async function startDive(mode) {
  clearTimer();
  state.mode = mode;
  state.dive = mode === "daily" ? dailySelection() : practiceSelection();
  state.index = 0;
  state.score = 0;
  state.results = [];
  $("header-score").textContent = "0";
  $("score").textContent = "0";
  $("depth").textContent = "0 m";
  $("mode-label").textContent = mode === "daily" ? "DAILY DIVE" : "PRACTICE DIVE";
  showScreen("game");
  await showQuestion();
}

async function showQuestion() {
  clearTimer();
  state.answered = false;
  state.seconds = SECONDS_PER_QUESTION;
  const question = state.dive[state.index];
  $("question-number").textContent = `${state.index + 1} / ${state.dive.length}`;
  $("progress-fill").style.width = `${(state.index / state.dive.length) * 100}%`;
  $("category").textContent = question.category || "General";
  $("question").textContent = "Loading question…";
  $("result").className = "result";
  $("result").textContent = "";
  $("next-button").hidden = true;
  $("answer-input").value = "";
  $("answer-input").disabled = true;
  $("submit-button").disabled = true;

  try {
    state.answers = await loadAnswers(question);
    state.answerMap = buildAnswerMap(state.answers);
    if (!state.answers.length) throw new Error("No answers available");
    $("question").textContent = question.question;
    $("answer-input").disabled = false;
    $("submit-button").disabled = false;
    $("answer-input").focus();
    renderTimer();
    state.timer = setInterval(tick, 1000);
  } catch (error) {
    console.error(error);
    $("question").textContent = question.question;
    $("result").className = "result bad";
    $("result").textContent = "This question could not load. Skip it and continue.";
    state.answered = true;
    $("next-button").hidden = false;
  }
}

function tick() {
  state.seconds -= 1;
  renderTimer();
  if (state.seconds <= 0) finishAttempt(null, true);
}

function renderTimer() {
  $("timer").textContent = String(Math.max(0, state.seconds));
  $("timer").classList.toggle("danger", state.seconds <= 5);
}

function clearTimer() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
}

function finishAttempt(answer, timedOut = false) {
  if (state.answered) return;
  state.answered = true;
  clearTimer();
  $("answer-input").disabled = true;
  $("submit-button").disabled = true;
  const question = state.dive[state.index];
  let points = 0;

  if (answer) {
    points = Number(answer.score) || 10;
    const label = SCORE_LABELS.get(points) || "Valid";
    state.score += points;
    $("result").className = "result good";
    $("result").textContent = `✓ ${answer.name} — ${label} · +${points} points`;
  } else {
    $("result").className = "result bad";
    $("result").textContent = timedOut ? "Time's up — 0 points" : "Not in the accepted answer set — 0 points";
  }

  state.results.push({ question: question.question, category: question.category || "general", points, answer: answer?.name || null });
  $("score").textContent = String(state.score);
  $("header-score").textContent = String(state.score);
  $("depth").textContent = `${(state.score * 10).toLocaleString()} m`;
  $("progress-fill").style.width = `${((state.index + 1) / state.dive.length) * 100}%`;
  $("next-button").textContent = state.index === state.dive.length - 1 ? "See result" : "Next question";
  $("next-button").hidden = false;
}

function submitAnswer(event) {
  event.preventDefault();
  if (state.answered) return;
  const input = $("answer-input").value;
  if (!input.trim()) return;
  finishAttempt(state.answerMap.get(normalizeAnswer(input)) || null, false);
}

async function nextQuestion() {
  if (!state.answered) return;
  state.index += 1;
  if (state.index >= state.dive.length) return finishDive();
  await showQuestion();
}

function finishDive() {
  clearTimer();
  if (state.mode === "daily") localStorage.setItem(`deep-answer-daily:${utcDateKey()}`, String(state.score));
  $("final-score").textContent = `${state.score} points`;
  $("final-depth").textContent = `${(state.score * 10).toLocaleString()} m deep`;
  $("breakdown").innerHTML = state.results.map((result, index) => `
    <div class="breakdown-row">
      <span class="mark">${result.points ? "✓" : "×"}</span>
      <span class="prompt">${index + 1}. ${escapeHtml(result.question)}</span>
      <span class="points">${result.points}</span>
    </div>`).join("");
  $("share-status").textContent = "";
  showScreen("end");
  updateDailyNote();
}

function escapeHtml(text) {
  return String(text).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

function shareText() {
  const marks = state.results.map((r) => r.points ? "●" : "○").join("");
  const mode = state.mode === "daily" ? `Daily ${utcDateKey()}` : "Practice";
  return `DEEP ANSWER — ${mode}\n${marks}\n${state.score} pts · ${(state.score * 10).toLocaleString()} m deep`;
}

async function copyResult() {
  const text = shareText();
  try {
    await navigator.clipboard.writeText(text);
    $("share-status").textContent = "Result copied.";
  } catch {
    $("share-status").textContent = text;
  }
}

$("daily-button").addEventListener("click", () => startDive("daily"));
$("practice-button").addEventListener("click", () => startDive("practice"));
$("answer-form").addEventListener("submit", submitAnswer);
$("next-button").addEventListener("click", nextQuestion);
$("share-button").addEventListener("click", copyResult);
$("again-button").addEventListener("click", () => startDive("practice"));

loadBank();
