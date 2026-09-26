const $ = (selector) => document.querySelector(selector);

const state = { jobId: null, cells: [], index: 0, polling: null };
const dimensions = [
  ["similarity", "Voice similarity", "Does this sound like the intended Pinocchio?"],
  ["naturalness", "Naturalness", "Does it sound like a person performing, not a model generating?"],
  ["character", "Character fit", "Does the voice feel believable for this puppet?"],
  ["funniness", "Funny delivery", "Do timing and emphasis help the joke land?"],
];

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function show(selector, visible = true) {
  $(selector).classList.toggle("hidden", !visible);
}

function roundSize() {
  return {
    configs: Number($("#config-count").value),
    lines: Number($("#line-count").value),
    seeds: Number($("#seed-count").value),
  };
}

// Keep this in step with MAX_CELLS in performance_lab.py.
const MAX_CELLS = 12;

function updateEstimate() {
  const { configs, lines, seeds } = roundSize();
  const cells = configs * lines;
  const clips = cells * seeds;
  const seconds = Math.round(clips * 2.8);
  const tooBig = cells > MAX_CELLS;
  $("#round-estimate").textContent = tooBig
    ? `${cells} groups to rate — too many`
    : `${clips} clips · about ${seconds} sec · ${cells} to rate`;
  $("#generate-button").disabled = tooBig;
  $("#compose-message").textContent = tooBig
    ? `That round would need ${cells} rated groups. Keep settings × lines at ${MAX_CELLS} or under.`
    : "";
}

function buildRatingGrid() {
  const grid = $("#rating-grid");
  grid.replaceChildren();
  for (const [key, label, help] of dimensions) {
    const row = document.createElement("div");
    row.className = "rating-row";
    row.innerHTML = `<div class="rating-copy"><strong>${label}</strong><small>${help}</small></div>`;
    const choices = document.createElement("div");
    choices.className = "likert";
    for (let value = 1; value <= 7; value += 1) {
      const item = document.createElement("label");
      item.innerHTML = `<input type="radio" name="${key}" value="${value}"><span>${value}</span>`;
      choices.append(item);
    }
    row.append(choices);
    grid.append(row);
  }
}

function resetRatings() {
  document.querySelectorAll("#rating-grid input").forEach((input) => { input.checked = false; });
  $("#rating-message").textContent = "";
}

function selectedRatings() {
  const ratings = {};
  for (const [key] of dimensions) {
    const input = document.querySelector(`input[name="${key}"]:checked`);
    if (!input) throw new Error("Give this group a score in all four rows.");
    ratings[key] = Number(input.value);
  }
  return ratings;
}

async function loadOptions() {
  try {
    const data = await request("/api/performance/options");
    if (!data.ready) throw new Error(data.error);
    $("#model-pill").classList.add("ready");
    $("#model-pill").lastChild.textContent = ` Chatterbox ready · ${data.current.referenceId}`;
    const row = $("#preset-row");
    for (const line of data.presets) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = line;
      button.title = line;
      button.addEventListener("click", () => { $("#performance-line").value = line; });
      row.append(button);
    }
  } catch (error) {
    $("#model-pill").lastChild.textContent = ` ${error.message}`;
    $("#compose-message").textContent = error.message;
  }
}

async function generateRound() {
  const button = $("#generate-button");
  button.disabled = true;
  $("#compose-message").textContent = "";
  show("#results-card", false);
  show("#audition-card", false);
  try {
    const data = await request("/api/performance/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: $("#performance-line").value,
        mode: document.querySelector('input[name="mode"]:checked').value,
        ...roundSize(),
      }),
    });
    state.jobId = data.jobId;
    show("#progress-card");
    $("#progress-card").scrollIntoView({ behavior: "smooth", block: "center" });
    await pollJob();
  } catch (error) {
    $("#compose-message").textContent = error.message;
    button.disabled = false;
  }
}

async function pollJob() {
  try {
    const job = await request(`/api/performance/job/${state.jobId}`);
    const percent = job.total ? Math.max(3, Math.round((job.completed / job.total) * 100)) : 3;
    $("#progress-fill").style.width = `${percent}%`;
    $("#progress-copy").textContent = job.status === "queued"
      ? "Waiting for the voice engine…"
      : `Rendered ${job.completed} of ${job.total} takes.`;
    if (job.status === "error") throw new Error(job.error || "Generation failed.");
    if (job.status === "ready") {
      state.cells = job.cells;
      state.index = 0;
      $("#progress-title").textContent = "Audition ready";
      $("#progress-fill").style.width = "100%";
      window.setTimeout(beginAudition, 350);
      return;
    }
    state.polling = window.setTimeout(pollJob, 750);
  } catch (error) {
    $("#progress-title").textContent = "Could not build this round";
    $("#progress-copy").textContent = error.message;
    $("#generate-button").disabled = false;
  }
}

function beginAudition() {
  show("#progress-card", false);
  show("#audition-card");
  renderCurrentCell();
  $("#audition-card").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCurrentCell() {
  const cell = state.cells[state.index];
  resetRatings();
  $("#clip-heading").textContent = `Group ${cell.id}`;
  $("#rating-counter").textContent = `${state.index + 1} of ${state.cells.length}`;
  $("#cell-line").textContent = cell.text;
  $("#save-rating").textContent = state.index === state.cells.length - 1
    ? "Save ratings & reveal results"
    : "Save ratings & hear next";

  const list = $("#take-list");
  list.replaceChildren();
  const stamp = Date.now();
  for (const take of cell.takes) {
    const item = document.createElement("div");
    item.className = "take-item";
    item.innerHTML = `<span class="take-label">Take ${take.index}</span>`;
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.preload = "auto";
    audio.src = `${take.audioUrl}?v=${stamp}`;
    item.append(audio);
    list.append(item);
  }
}

async function saveRating() {
  const button = $("#save-rating");
  button.disabled = true;
  try {
    const cell = state.cells[state.index];
    await request("/api/performance/rate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId: state.jobId, cellId: cell.id, ratings: selectedRatings() }),
    });
    if (state.index < state.cells.length - 1) {
      state.index += 1;
      renderCurrentCell();
      $("#take-list").scrollIntoView({ behavior: "smooth", block: "center" });
    } else {
      await revealResults();
    }
  } catch (error) {
    $("#rating-message").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function revealResults() {
  const data = await request(`/api/performance/results?job_id=${encodeURIComponent(state.jobId)}`);
  const list = $("#results-list");
  list.replaceChildren();
  data.results.forEach((result, index) => {
    const item = document.createElement("article");
    item.className = `result-item${index === 0 ? " winner" : ""}`;
    const settings = result.settings;
    const lines = result.lines
      .map((line) => `<li><span>${line.label}</span><strong>${line.score.toFixed(2)}</strong></li>`)
      .join("");
    item.innerHTML = `
      <span class="rank">#${index + 1}${index === 0 ? " · WINNER" : ""}</span>
      <span class="clip-badge">${result.configId}</span>
      <div class="score"><strong>${result.score.toFixed(2)} / 7</strong>
        <small>spread ${result.spread.toFixed(2)} · worst line ${result.worst.toFixed(2)}</small>
        <ul class="line-breakdown">${lines}</ul>
        <p class="setting-line">${settings.referenceId} · temp ${settings.temperature} · repeat ${settings.repetitionPenalty}<br>top-p ${settings.topP} · top-k ${settings.topK} · seeds ${data.seeds.join(", ")}</p>
      </div>`;
    const apply = document.createElement("button");
    apply.className = "secondary-button apply-button";
    apply.type = "button";
    apply.textContent = index === 0 ? "Apply winner" : "Apply this";
    apply.addEventListener("click", () => applyConfig(result.configId, apply));
    item.append(apply);
    list.append(item);
  });
  show("#audition-card", false);
  show("#results-card");
  $("#results-card").scrollIntoView({ behavior: "smooth", block: "start" });
  $("#generate-button").disabled = false;
}

async function applyConfig(configId, button) {
  $("#results-message").textContent = "";
  button.disabled = true;
  try {
    const data = await request("/api/performance/apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId: state.jobId, configId }),
    });
    document.querySelectorAll(".apply-button").forEach((item) => {
      item.classList.remove("applied");
      item.textContent = item === button ? "Applied ✓" : "Apply this";
    });
    button.classList.add("applied");
    $("#results-message").style.color = "var(--green)";
    $("#results-message").textContent = `Live voice updated: ${data.voice}`;
  } catch (error) {
    $("#results-message").style.color = "var(--red)";
    $("#results-message").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

function newRound() {
  show("#results-card", false);
  $("#compose-card").scrollIntoView({ behavior: "smooth", block: "start" });
}

buildRatingGrid();
loadOptions();
updateEstimate();
$("#generate-button").addEventListener("click", generateRound);
$("#save-rating").addEventListener("click", saveRating);
$("#new-round").addEventListener("click", newRound);
for (const id of ["#config-count", "#line-count", "#seed-count"]) {
  $(id).addEventListener("change", updateEstimate);
}
