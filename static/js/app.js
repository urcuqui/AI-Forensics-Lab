(function () {
  "use strict";

  const appEl = document.getElementById("app");
  const CSRF_TOKEN = appEl.dataset.csrf;

  const STAGES = ["case", "evidence", "principles", "findings", "conclusion"];
  let furthestIndex = 0;

  // -------------------------------------------------------------------
  // Fetch helper
  // -------------------------------------------------------------------
  async function api(url, options = {}) {
    const opts = Object.assign({ headers: {} }, options);
    opts.headers["Content-Type"] = "application/json";
    if (options.method && options.method !== "GET") {
      opts.headers["X-CSRF-Token"] = CSRF_TOKEN;
    }
    const resp = await fetch(url, opts);
    let body;
    try {
      body = await resp.json();
    } catch (e) {
      body = null;
    }
    if (!resp.ok) {
      const message = (body && body.error) || `Request failed (${resp.status})`;
      throw new Error(message);
    }
    return body;
  }

  function esc(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  // -------------------------------------------------------------------
  // Stage navigation
  // -------------------------------------------------------------------
  function showStage(name) {
    document.querySelectorAll(".stage").forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.stagePanel !== name);
    });
    document.querySelectorAll(".progress-step").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.stage === name);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function goToStage(name) {
    const idx = STAGES.indexOf(name);
    if (idx < 0) return;
    if (idx > furthestIndex) furthestIndex = idx;
    document.querySelectorAll(".progress-step").forEach((btn) => {
      const bIdx = STAGES.indexOf(btn.dataset.stage);
      if (bIdx <= furthestIndex) {
        btn.disabled = false;
        btn.classList.toggle("complete", bIdx < idx);
      }
    });
    showStage(name);
  }

  document.getElementById("progress-track").addEventListener("click", (e) => {
    const btn = e.target.closest(".progress-step");
    if (!btn || btn.disabled) return;
    goToStage(btn.dataset.stage);
  });

  document.getElementById("btn-start-assessment").addEventListener("click", () => goToStage("evidence"));

  document.querySelectorAll("[data-continue]").forEach((btn) => {
    btn.addEventListener("click", () => goToStage(btn.dataset.continue));
  });

  // -------------------------------------------------------------------
  // Ollama status
  // -------------------------------------------------------------------
  async function loadOllamaStatus() {
    const pill = document.getElementById("ollama-indicator");
    try {
      const data = await api("/api/ollama-status");
      pill.textContent = "Ollama: " + (data.connected ? "connected" : "unavailable");
      pill.title = data.message;
      pill.className = "status-pill secondary-control " + (data.connected ? "status-ok" : "status-bad");
    } catch (e) {
      pill.textContent = "Ollama: unavailable";
      pill.className = "status-pill secondary-control status-bad";
    }
  }

  // -------------------------------------------------------------------
  // Evidence interactions
  // -------------------------------------------------------------------
  function refreshEvidenceCard(id, data) {
    const card = document.querySelector(`.evidence-card[data-evidence-id="${id}"]`);
    if (!card) return;
    const badges = card.querySelector(".evidence-badges");
    badges.innerHTML =
      (data.flagged ? '<span class="badge badge-flagged">Flagged</span>' : "") +
      (data.relevant ? '<span class="badge badge-relevant">Relevant</span>' : "");
    const relevantBtn = card.querySelector('[data-action="relevant"]');
    if (relevantBtn) relevantBtn.textContent = data.relevant ? "Unmark Relevant" : "Mark Relevant";
    const flagBtn = card.querySelector('[data-action="flag"]');
    if (flagBtn) flagBtn.textContent = data.flagged ? "Unflag Suspicious" : "Flag Suspicious";
    const notesList = document.getElementById(`notes-${id}`);
    if (notesList) {
      notesList.innerHTML = (data.notes || []).length
        ? data.notes.map((n) => `<div class="note-item">${esc(n.note_text)}</div>`).join("")
        : '<span class="muted">No notes yet.</span>';
    }
  }

  document.getElementById("stage-evidence").addEventListener("click", async (e) => {
    const toggleBtn = e.target.closest(".evidence-card-toggle");
    if (toggleBtn) {
      const id = toggleBtn.dataset.toggleEvidence;
      const body = document.getElementById(`evidence-body-${id}`);
      const card = toggleBtn.closest(".evidence-card");
      const willShow = body.hasAttribute("hidden");
      if (willShow) body.removeAttribute("hidden");
      else body.setAttribute("hidden", "");
      card.classList.toggle("expanded", willShow);
      return;
    }

    const inspectBtn = e.target.closest("#btn-inspect-document");
    if (inspectBtn) {
      const id = inspectBtn.dataset.evidenceId;
      const block = document.getElementById(`injected-${id}`);
      const reveal = document.getElementById(`injection-reveal-${id}`);
      if (block) block.classList.add("highlighted");
      if (reveal) reveal.classList.remove("hidden");
      inspectBtn.disabled = true;
      return;
    }

    const actionBtn = e.target.closest("[data-action]");
    if (!actionBtn) return;
    const id = actionBtn.dataset.evidenceId;
    const action = actionBtn.dataset.action;

    try {
      if (action === "relevant" || action === "flag") {
        const key = action === "relevant" ? "relevant" : "flagged";
        const currentlyOn = /^Unmark|^Unflag/.test(actionBtn.textContent.trim());
        const payload = {};
        payload[key] = !currentlyOn;
        const data = await api(`/api/evidence/${id}/flag`, { method: "POST", body: JSON.stringify(payload) });
        refreshEvidenceCard(id, data);
      } else if (action === "add-note") {
        const textarea = document.getElementById(`note-input-${id}`);
        const text = textarea.value.trim();
        if (!text) return;
        const data = await api(`/api/evidence/${id}/note`, { method: "POST", body: JSON.stringify({ note: text }) });
        refreshEvidenceCard(id, data);
        textarea.value = "";
      }
    } catch (err) {
      alert("Could not save: " + err.message);
    }
  });

  // -------------------------------------------------------------------
  // Principles / Audience Mode
  // -------------------------------------------------------------------
  let audienceMode = false;

  document.getElementById("btn-audience-mode").addEventListener("click", (e) => {
    audienceMode = !audienceMode;
    e.target.textContent = "Audience Mode: " + (audienceMode ? "On" : "Off");
    document.querySelectorAll(".principle-card").forEach((card) => {
      const picker = card.querySelector(".audience-picker");
      const result = card.querySelector(".principle-result");
      const label = card.querySelector(".recommended-label");
      if (audienceMode) {
        picker.classList.remove("hidden");
        result.classList.add("hidden");
        label.classList.add("hidden");
      } else {
        picker.classList.add("hidden");
        result.classList.remove("hidden");
      }
    });
  });

  document.getElementById("stage-principles").addEventListener("click", (e) => {
    const choiceBtn = e.target.closest(".audience-choice");
    if (!choiceBtn) return;
    const card = choiceBtn.closest(".principle-card");
    card.querySelector(".audience-picker").classList.add("hidden");
    card.querySelector(".principle-result").classList.remove("hidden");
    card.querySelector(".recommended-label").classList.remove("hidden");
  });

  // -------------------------------------------------------------------
  // AI-assisted analysis
  // -------------------------------------------------------------------
  document.getElementById("btn-analyse").addEventListener("click", async () => {
    const statusEl = document.getElementById("analysis-status");
    const resultsEl = document.getElementById("analysis-results");
    statusEl.textContent = "Analysing with local model…";
    resultsEl.innerHTML = "";
    try {
      const data = await api("/api/analyse", { method: "POST", body: JSON.stringify({}) });
      statusEl.textContent = "";
      renderAnalysisResults(data);
    } catch (err) {
      statusEl.textContent = "Analysis unavailable: " + err.message;
    }
  });

  function renderAnalysisResults(data) {
    const resultsEl = document.getElementById("analysis-results");
    const section = (cls, title, items) =>
      `<div class="analysis-section analysis-${cls}">
        <h4>${title}</h4>
        ${items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : '<div class="muted">None reported.</div>'}
      </div>`;
    resultsEl.innerHTML =
      section("observations", "FACT — Observations", data.observations) +
      section("concerns", "Potential Concerns", data.potential_concerns) +
      section("principles", "Affected CEPEJ Principles", data.affected_principles) +
      section("supporting", "Supporting Evidence", data.supporting_evidence) +
      section("missing", "Missing Information", data.missing_information) +
      section("alternatives", "HYPOTHESIS — Alternative Explanations", data.alternative_explanations) +
      `<div class="callout callout-warning">This is AI-assisted analysis support. The investigator must
        independently verify every item above before relying on it.</div>`;
  }

  // -------------------------------------------------------------------
  // Conclusion stage
  // -------------------------------------------------------------------
  document.getElementById("btn-show-forensic-evidence").addEventListener("click", (e) => {
    const simple = document.getElementById("evidence-model-simple");
    const expanded = document.getElementById("evidence-model-expanded");
    const showingExpanded = expanded.classList.toggle("hidden") === false;
    simple.classList.toggle("hidden", showingExpanded);
    e.target.textContent = showingExpanded ? "Show simple view" : "Show forensic evidence";
  });

  document.getElementById("btn-restart").addEventListener("click", async () => {
    try {
      await api("/api/reset", { method: "POST" });
    } catch (err) {
      // proceed with reload regardless
    }
    location.reload();
  });

  // -------------------------------------------------------------------
  // Presentation mode + language toggle
  // -------------------------------------------------------------------
  document.getElementById("btn-presentation").addEventListener("click", () => {
    document.body.classList.toggle("presentation");
  });

  document.getElementById("btn-lang").addEventListener("click", (e) => {
    const en = document.getElementById("subtitle-en");
    const es = document.getElementById("subtitle-es");
    const goingToEs = es.hidden;
    en.hidden = goingToEs;
    es.hidden = !goingToEs;
    e.target.textContent = goingToEs ? "English" : "Español";
  });

  // -------------------------------------------------------------------
  // Init
  // -------------------------------------------------------------------
  loadOllamaStatus();
})();
