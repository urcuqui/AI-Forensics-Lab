(function () {
  "use strict";

  const appEl = document.getElementById("app");
  const CSRF_TOKEN = appEl.dataset.csrf;

  const state = {
    evidence: [],
    evidenceById: {},
    trace: null,
    timeline: [],
    timelineActorFilter: null,
    findings: [],
    suggestedFindings: [],
    rootCause: null,
    guidedSteps: [],
    guidedIndex: 0,
    guidedActive: false,
    lastReport: null,
  };

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
  function switchStage(stageName) {
    document.querySelectorAll(".stage-tab").forEach((tab) => {
      tab.classList.toggle("active", tab.dataset.stage === stageName);
    });
    document.querySelectorAll(".stage").forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.stagePanel !== stageName);
    });
  }

  document.getElementById("stage-nav").addEventListener("click", (e) => {
    const tab = e.target.closest(".stage-tab");
    if (!tab) return;
    document.querySelectorAll(".stage-tab").forEach((t) => {
      if (t === tab) return;
      if (t.dataset.stage !== tab.dataset.stage) t.classList.add("complete");
    });
    switchStage(tab.dataset.stage);
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
      pill.className = "status-pill " + (data.connected ? "status-ok" : "status-bad");
    } catch (e) {
      pill.textContent = "Ollama: unavailable";
      pill.className = "status-pill status-bad";
    }
  }

  // -------------------------------------------------------------------
  // Evidence
  // -------------------------------------------------------------------
  async function loadEvidence() {
    const data = await api("/api/evidence");
    state.evidence = data.evidence;
    state.evidenceById = {};
    data.evidence.forEach((e) => (state.evidenceById[e.id] = e));
    renderEvidenceGrid();
    renderInjectionSelect();
    renderAnalysisCheckboxes();
    renderFindingEvidenceRefs();
  }

  function renderEvidenceGrid() {
    const grid = document.getElementById("evidence-grid");
    document.getElementById("evidence-count-label").textContent =
      state.evidence.length + " artefacts";
    grid.innerHTML = state.evidence
      .map(
        (e) => `
      <div class="evidence-card" data-evidence-id="${e.id}">
        <div class="evidence-card-head">
          <span class="evidence-id">${e.id}</span>
          <span class="evidence-type">${esc(e.type)}</span>
        </div>
        <div class="evidence-desc">${esc(e.description)}</div>
        <div class="evidence-meta-row">
          <span>${esc(e.timestamp)}</span>
          ${e.flagged ? '<span class="badge badge-flagged">Flagged</span>' : ""}
          ${e.relevant ? '<span class="badge badge-relevant">Relevant</span>' : ""}
        </div>
      </div>`
      )
      .join("");
    grid.querySelectorAll(".evidence-card").forEach((card) => {
      card.addEventListener("click", () => openEvidenceModal(card.dataset.evidenceId));
    });
  }

  function openEvidenceModal(evidenceId) {
    const e = state.evidenceById[evidenceId];
    if (!e) return;
    const modal = document.getElementById("evidence-modal");
    const body = document.getElementById("evidence-modal-body");
    body.innerHTML = `
      <span class="origin-flag origin-original">Original Evidence</span>
      <h2>${e.id} — ${esc(e.type)}</h2>
      <div class="evidence-detail-section">
        <div class="evidence-detail-label">Metadata</div>
        <div class="muted">Source: ${esc(e.source)}<br>Timestamp: ${esc(e.timestamp)}<br>
        Integrity status: ${esc(e.integrity_status)}</div>
      </div>
      <div class="evidence-detail-section">
        <div class="evidence-detail-label">SHA-256</div>
        <div class="hash-box">${esc(e.sha256)}</div>
      </div>
      <div class="evidence-detail-section">
        <div class="evidence-detail-label">Description</div>
        <div>${esc(e.description)}</div>
      </div>
      <div class="evidence-detail-section">
        <div class="evidence-detail-label">Raw Content</div>
        <div class="evidence-raw">${esc(e.content)}</div>
      </div>
      <div class="evidence-detail-section row gap">
        <button class="btn btn-outline btn-small" id="modal-flag-suspicious">
          ${e.flagged ? "Unflag Suspicious" : "Flag Suspicious"}
        </button>
        <button class="btn btn-outline btn-small" id="modal-mark-relevant">
          ${e.relevant ? "Unmark Relevant" : "Mark Relevant"}
        </button>
      </div>
      <div class="evidence-detail-section">
        <span class="origin-flag origin-notes">Investigator Notes</span>
        <div class="note-list" id="modal-note-list">
          ${(e.notes || [])
            .map(
              (n) => `<div class="note-item">${esc(n.note_text)}<div class="note-time">${new Date(
                n.created_at * 1000
              ).toLocaleString()}</div></div>`
            )
            .join("") || '<span class="muted">No notes yet.</span>'}
        </div>
        <textarea id="modal-note-input" placeholder="Add an investigator note (does not modify original evidence)..."></textarea>
        <button class="btn btn-primary btn-small" id="modal-add-note">Add Note</button>
      </div>
    `;
    modal.classList.remove("hidden");

    body.querySelector("#modal-flag-suspicious").addEventListener("click", async () => {
      await api(`/api/evidence/${e.id}/flag`, {
        method: "POST",
        body: JSON.stringify({ flagged: !e.flagged }),
      });
      await loadEvidence();
      openEvidenceModal(e.id);
    });
    body.querySelector("#modal-mark-relevant").addEventListener("click", async () => {
      await api(`/api/evidence/${e.id}/flag`, {
        method: "POST",
        body: JSON.stringify({ relevant: !e.relevant }),
      });
      await loadEvidence();
      openEvidenceModal(e.id);
    });
    body.querySelector("#modal-add-note").addEventListener("click", async () => {
      const input = body.querySelector("#modal-note-input");
      const text = input.value.trim();
      if (!text) return;
      await api(`/api/evidence/${e.id}/note`, {
        method: "POST",
        body: JSON.stringify({ note: text }),
      });
      await loadEvidence();
      openEvidenceModal(e.id);
    });
  }

  document.getElementById("evidence-modal-close").addEventListener("click", closeEvidenceModal);
  document.getElementById("evidence-modal-backdrop").addEventListener("click", closeEvidenceModal);
  function closeEvidenceModal() {
    document.getElementById("evidence-modal").classList.add("hidden");
  }

  // -------------------------------------------------------------------
  // Prompt injection detector
  // -------------------------------------------------------------------
  function renderInjectionSelect() {
    const select = document.getElementById("injection-evidence-select");
    select.innerHTML = state.evidence
      .map((e) => `<option value="${e.id}">${e.id} — ${esc(e.type)}</option>`)
      .join("");
    const preferred = state.evidence.find((e) => e.tags.includes("untrusted-content"));
    if (preferred) select.value = preferred.id;
  }

  document.getElementById("btn-run-injection-scan").addEventListener("click", async () => {
    const evidenceId = document.getElementById("injection-evidence-select").value;
    const resultsEl = document.getElementById("injection-results");
    resultsEl.innerHTML = '<span class="muted">Analysing…</span>';
    try {
      const data = await api("/api/detect-injection", {
        method: "POST",
        body: JSON.stringify({ evidence_id: evidenceId }),
      });
      renderInjectionResults(data);
    } catch (e) {
      resultsEl.innerHTML = `<span class="muted">Analysis failed: ${esc(e.message)}</span>`;
    }
  });

  function renderInjectionResults(data) {
    const resultsEl = document.getElementById("injection-results");
    const heuristic = data.heuristic_findings || [];
    let html = "";
    if (heuristic.length === 0 && (!data.ai_findings || data.ai_findings.findings.length === 0)) {
      html += `<div class="muted">No suspicious instruction-like language detected by heuristic scan.</div>`;
    }
    if (heuristic.length > 0) {
      html += `<h4 class="muted">Heuristic Scan — Potential Prompt Injection Detected</h4>`;
      heuristic.forEach((f) => {
        html += `<div class="injection-finding">
          <div class="finding-title">Potential prompt injection detected (evidence ${esc(
            data.evidence_id
          )})</div>
          <div class="finding-text">"${esc(f.text)}"</div>
          <div class="muted">Context: …${esc(f.context)}…</div>
          <div class="finding-reason">${esc(f.reason)}</div>
        </div>`;
      });
    }
    if (data.ai_findings) {
      html += `<h4 class="muted">AI-Assisted Review</h4>`;
      if (data.ai_findings.findings.length === 0) {
        html += `<div class="muted">The model reported no additional suspicious spans.</div>`;
      }
      data.ai_findings.findings.forEach((f) => {
        html += `<div class="injection-finding">
          <div class="finding-title">Potential prompt injection detected</div>
          <div class="finding-text">"${esc(f.text)}"</div>
          <div class="muted">Context: ${esc(f.context)}</div>
          <div class="finding-reason">${esc(f.reason)}</div>
        </div>`;
      });
      if (data.ai_findings.overall_assessment) {
        html += `<div class="muted">Model assessment: ${esc(
          data.ai_findings.overall_assessment
        )}</div>`;
      }
    } else if (data.ai_error) {
      html += `<div class="muted">AI-assisted review unavailable: ${esc(data.ai_error)}</div>`;
    }
    resultsEl.innerHTML = html;
  }

  // -------------------------------------------------------------------
  // Trace diagram
  // -------------------------------------------------------------------
  async function loadTrace() {
    state.trace = await api("/api/trace");
    renderTraceDiagram();
  }

  function renderTraceDiagram() {
    const container = document.getElementById("trace-diagram");
    const nodes = state.trace.nodes;
    let html = "";
    nodes.forEach((n, i) => {
      html += `<div class="trace-node trust-${n.trust}" data-node-id="${n.id}">
        ${n.label}<small>${n.trust === "trusted" ? "Trusted" : n.trust === "untrusted" ? "Untrusted" : "Model-generated"}</small>
      </div>`;
      if (i < nodes.length - 1) html += `<div class="trace-arrow">↓</div>`;
    });
    container.innerHTML = html;
    container.querySelectorAll(".trace-node").forEach((el) => {
      el.addEventListener("click", () => selectTraceNode(el.dataset.nodeId));
    });
  }

  function selectTraceNode(nodeId) {
    document.querySelectorAll(".trace-node").forEach((el) => {
      el.classList.toggle("selected", el.dataset.nodeId === nodeId);
    });
    const node = state.trace.nodes.find((n) => n.id === nodeId);
    const detail = document.getElementById("trace-detail-content");
    if (!node) return;
    const evidenceLinks = node.evidence_refs
      .map(
        (id) =>
          `<button class="btn btn-outline btn-small trace-evidence-link" data-evidence-id="${id}">${id}</button>`
      )
      .join(" ");
    detail.innerHTML = `
      <h3>${node.label} <span class="tag-soft">${node.trust}</span></h3>
      <p>${esc(node.note)}</p>
      <div class="row gap wrap">${evidenceLinks}</div>
    `;
    detail.querySelectorAll(".trace-evidence-link").forEach((btn) => {
      btn.addEventListener("click", () => openEvidenceModal(btn.dataset.evidenceId));
    });
  }

  document.getElementById("btn-trust-boundaries").addEventListener("click", () => {
    const panel = document.getElementById("trust-boundary-panel");
    const diagram = document.getElementById("trace-diagram");
    const showing = panel.classList.toggle("hidden") === false;
    diagram.classList.toggle("show-boundaries", showing);
    if (showing) {
      panel.innerHTML =
        `<div class="muted" style="margin-bottom:6px;">A trust boundary is a point where information crosses between components with different levels of trust.</div>` +
        state.trace.trust_boundaries
          .map(
            (b) =>
              `<div class="trust-boundary-item"><strong>${esc(b.from)} → ${esc(
                b.to
              )}</strong><br>${esc(b.description)}</div>`
          )
          .join("");
    }
  });

  // -------------------------------------------------------------------
  // Timeline
  // -------------------------------------------------------------------
  async function loadTimeline() {
    const data = await api("/api/timeline");
    state.timeline = data.timeline;
    renderTimelineFilters(data.actors);
    renderTimelineList();
  }

  function renderTimelineFilters(actors) {
    const container = document.getElementById("timeline-filters");
    container.innerHTML =
      `<span class="filter-chip ${!state.timelineActorFilter ? "active" : ""}" data-actor="">All</span>` +
      actors
        .map(
          (a) =>
            `<span class="filter-chip ${state.timelineActorFilter === a ? "active" : ""}" data-actor="${a}">${a}</span>`
        )
        .join("");
    container.querySelectorAll(".filter-chip").forEach((chip) => {
      chip.addEventListener("click", async () => {
        state.timelineActorFilter = chip.dataset.actor || null;
        const data = await api(
          "/api/timeline" + (state.timelineActorFilter ? `?actor=${encodeURIComponent(state.timelineActorFilter)}` : "")
        );
        state.timeline = data.timeline;
        renderTimelineFilters(data.actors);
        renderTimelineList();
      });
    });
  }

  function renderTimelineList() {
    const list = document.getElementById("timeline-list");
    list.innerHTML = state.timeline
      .map(
        (t) => `
      <div class="timeline-item" data-evidence-id="${t.evidence_ref}">
        <span class="timeline-time">${esc(t.time)}</span>
        <span class="actor-pill actor-${t.actor}">${t.actor}</span>
        <span>${esc(t.description)}</span>
      </div>`
      )
      .join("");
    list.querySelectorAll(".timeline-item").forEach((item) => {
      item.addEventListener("click", () => openEvidenceModal(item.dataset.evidenceId));
    });
  }

  // -------------------------------------------------------------------
  // Custody + evidence map (Stage 1)
  // -------------------------------------------------------------------
  async function loadCustody() {
    const data = await api("/api/custody");
    document.getElementById("custody-flow").innerHTML = data.stages
      .map((s, i, arr) => `<span class="flow-node">${esc(s)}</span>` + (i < arr.length - 1 ? '<span class="flow-arrow">→</span>' : ""))
      .join("");
    const rows = data.evidence
      .map(
        (e) => `<tr>
        <td>${e.id}</td><td>${esc(e.acquisition_timestamp)}</td>
        <td><code>${e.sha256.slice(0, 20)}…</code></td>
        <td>${esc(e.source)}</td><td>${esc(e.investigator)}</td>
        <td>${esc(e.integrity_status)}</td>
      </tr>`
      )
      .join("");
    document.getElementById("custody-table-wrap").innerHTML = `
      <table class="forensic-table">
        <thead><tr><th>ID</th><th>Acquired</th><th>SHA-256</th><th>Source</th><th>Investigator</th><th>Integrity</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  async function loadEvidenceMap() {
    const data = await api("/api/evidence-map");
    const container = document.getElementById("evidence-map");
    container.innerHTML = Object.entries(data.map)
      .map(
        ([block, items]) => `
      <div class="map-block">
        <h4>${esc(block)}</h4>
        <ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>
      </div>`
      )
      .join("");
  }

  // -------------------------------------------------------------------
  // AI-assisted analysis
  // -------------------------------------------------------------------
  function renderAnalysisCheckboxes() {
    const container = document.getElementById("analysis-evidence-select");
    container.innerHTML = state.evidence
      .map(
        (e) => `<label class="checkbox-item">
        <input type="checkbox" value="${e.id}" class="analysis-checkbox"> ${e.id} — ${esc(e.type)}
      </label>`
      )
      .join("");
  }

  document.getElementById("btn-analyse-selected").addEventListener("click", async () => {
    const ids = Array.from(document.querySelectorAll(".analysis-checkbox:checked")).map((c) => c.value);
    const statusEl = document.getElementById("analysis-status");
    const resultsEl = document.getElementById("analysis-results");
    if (ids.length === 0) {
      statusEl.textContent = "Select at least one evidence artefact.";
      return;
    }
    statusEl.textContent = "Analysing with local model…";
    resultsEl.innerHTML = "";
    try {
      const data = await api("/api/analyse", {
        method: "POST",
        body: JSON.stringify({ evidence_ids: ids }),
      });
      statusEl.textContent = "";
      renderAnalysisResults(data);
    } catch (e) {
      statusEl.textContent = "Analysis failed: " + e.message;
    }
  });

  function renderAnalysisResults(data) {
    const resultsEl = document.getElementById("analysis-results");
    const section = (cls, title, items) =>
      `<div class="analysis-section analysis-${cls}">
        <h4>${title}</h4>
        ${items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : '<div class="muted">None reported.</div>'}
      </div>`;
    resultsEl.innerHTML = `
      <div>Model confidence: <span class="confidence-badge confidence-${data.confidence}">${data.confidence}</span></div>
      ${section("observations", "FACT — Observations", data.observations)}
      ${section("suspicious", "Suspicious Patterns", data.suspicious_elements)}
      ${section("injection", "Possible Prompt Injection", data.possible_prompt_injection)}
      ${section("contradictions", "Contradictions", data.contradictions)}
      ${section("missing", "Missing Evidence", data.missing_evidence)}
      ${section("hypotheses", "HYPOTHESIS — Not Confirmed Fact", data.hypotheses)}
      <div class="callout callout-warning">This is AI-assisted analysis support. The investigator must
        independently verify every item above before relying on it.</div>
    `;
  }

  // -------------------------------------------------------------------
  // Findings board
  // -------------------------------------------------------------------
  function renderFindingEvidenceRefs() {
    const container = document.getElementById("f-evidence-refs");
    container.innerHTML = state.evidence
      .map(
        (e) => `<label class="checkbox-item"><input type="checkbox" value="${e.id}" class="f-ref-checkbox"> ${e.id}</label>`
      )
      .join("");
  }

  async function loadCategories() {
    const select = document.getElementById("f-category");
    const categories = [
      "Prompt Injection", "RAG Poisoning", "Memory Contamination",
      "Excessive Agency", "Improper Tool Use", "Hallucination",
      "Logging Gap", "Provenance Failure", "Configuration Error",
      "Insufficient Evidence",
    ];
    select.innerHTML = categories.map((c) => `<option>${c}</option>`).join("");
  }

  async function loadFindings() {
    const data = await api("/api/findings");
    state.findings = data.findings;
    state.suggestedFindings = data.suggested;
    renderSuggestedFindings();
    renderFindingsList();
  }

  function renderSuggestedFindings() {
    const container = document.getElementById("suggested-findings");
    container.innerHTML = state.suggestedFindings
      .map(
        (f, i) => `<div class="suggested-card">
        <h4>${esc(f.title)}</h4>
        <div class="muted">${esc(f.category)} · Severity: ${esc(f.severity)}</div>
        <button class="btn btn-outline btn-small" data-suggested-index="${i}">Use as Template</button>
      </div>`
      )
      .join("");
    container.querySelectorAll("[data-suggested-index]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const f = state.suggestedFindings[btn.dataset.suggestedIndex];
        document.getElementById("f-title").value = f.title;
        document.getElementById("f-category").value = f.category;
        document.getElementById("f-severity").value = f.severity;
        document.getElementById("f-confidence").value = f.confidence;
        document.getElementById("f-observation").value = f.observation;
        document.getElementById("f-interpretation").value = f.interpretation;
        document.querySelectorAll(".f-ref-checkbox").forEach((cb) => {
          cb.checked = f.evidence_refs.includes(cb.value);
        });
        document.getElementById("finding-form").scrollIntoView({ behavior: "smooth" });
      });
    });
  }

  function renderFindingsList() {
    const list = document.getElementById("findings-list");
    if (state.findings.length === 0) {
      list.innerHTML = '<div class="muted">No findings recorded yet.</div>';
      return;
    }
    list.innerHTML = state.findings
      .map(
        (f) => `<div class="finding-card sev-${f.severity}">
        <div class="finding-card-head">
          <h4>${f.finding_id} — ${esc(f.title)}</h4>
          <button class="btn btn-outline btn-small" data-delete-finding="${f.id}">Delete</button>
        </div>
        <div class="finding-meta">${esc(f.category)} · Severity: ${esc(f.severity)} · Confidence: ${esc(
          f.confidence
        )} · Evidence: ${f.evidence_refs.join(", ")}</div>
        <div class="finding-body-row"><strong>Observation:</strong> ${esc(f.observation)}</div>
        <div class="finding-body-row"><strong>Interpretation:</strong> ${esc(f.interpretation)}</div>
        ${f.investigator_notes ? `<div class="finding-body-row"><strong>Notes:</strong> ${esc(f.investigator_notes)}</div>` : ""}
      </div>`
      )
      .join("");
    list.querySelectorAll("[data-delete-finding]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await api(`/api/findings/${btn.dataset.deleteFinding}`, { method: "DELETE" });
        await loadFindings();
      });
    });
  }

  document.getElementById("finding-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const evidenceRefs = Array.from(document.querySelectorAll(".f-ref-checkbox:checked")).map((c) => c.value);
    try {
      await api("/api/findings", {
        method: "POST",
        body: JSON.stringify({
          title: document.getElementById("f-title").value,
          category: document.getElementById("f-category").value,
          severity: document.getElementById("f-severity").value,
          confidence: document.getElementById("f-confidence").value,
          evidence_refs: evidenceRefs,
          observation: document.getElementById("f-observation").value,
          interpretation: document.getElementById("f-interpretation").value,
          investigator_notes: document.getElementById("f-notes").value,
        }),
      });
      e.target.reset();
      document.querySelectorAll(".f-ref-checkbox").forEach((cb) => (cb.checked = false));
      await loadFindings();
    } catch (err) {
      alert("Could not save finding: " + err.message);
    }
  });

  // -------------------------------------------------------------------
  // Root cause
  // -------------------------------------------------------------------
  async function loadRootCause() {
    const data = await api("/api/root-cause");
    state.rootCause = data;
    renderRootCauseOptions(data);
  }

  function renderRootCauseOptions(data) {
    const container = document.getElementById("root-cause-options");
    const selected = data.selection ? data.selection.selected_option : null;
    container.innerHTML = data.options
      .map((opt) => {
        const isRecommended = opt === data.suggested.recommended_option;
        const isSelected = opt === selected;
        return `<div class="root-cause-option ${isSelected ? "selected" : ""} ${
          isRecommended ? "recommended" : ""
        }" data-option="${esc(opt)}">${esc(opt)}</div>`;
      })
      .join("");
    container.querySelectorAll(".root-cause-option").forEach((el) => {
      el.addEventListener("click", () => {
        container.querySelectorAll(".root-cause-option").forEach((o) => o.classList.remove("selected"));
        el.classList.add("selected");
      });
    });
    if (data.selection) {
      document.getElementById("rc-primary").value = data.selection.primary_cause || "";
      document.getElementById("rc-contributing").value = (data.selection.contributing_causes || []).join(", ");
      document.getElementById("rc-justification").value = data.selection.justification || "";
    }
  }

  document.getElementById("btn-save-root-cause").addEventListener("click", async () => {
    const selectedEl = document.querySelector(".root-cause-option.selected");
    if (!selectedEl) {
      alert("Select a root cause classification first.");
      return;
    }
    const contributing = document
      .getElementById("rc-contributing")
      .value.split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    try {
      await api("/api/root-cause", {
        method: "POST",
        body: JSON.stringify({
          selected_option: selectedEl.dataset.option,
          primary_cause: document.getElementById("rc-primary").value,
          contributing_causes: contributing,
          justification: document.getElementById("rc-justification").value,
        }),
      });
      document.getElementById("root-cause-saved").textContent = "Root cause classification saved.";
    } catch (e) {
      alert("Could not save root cause: " + e.message);
    }
  });

  // -------------------------------------------------------------------
  // Report generation
  // -------------------------------------------------------------------
  document.getElementById("btn-generate-report").addEventListener("click", async () => {
    const preview = document.getElementById("report-preview");
    preview.textContent = "Generating…";
    try {
      const data = await api("/api/report", {
        method: "POST",
        body: JSON.stringify({ format: "markdown" }),
      });
      state.lastReport = data;
      preview.textContent = data.content;
      document.getElementById("btn-export-md").disabled = false;
      document.getElementById("btn-export-html").disabled = false;
    } catch (e) {
      preview.textContent = "Report generation failed: " + e.message;
    }
  });

  document.getElementById("btn-export-md").addEventListener("click", () => downloadReport("markdown"));
  document.getElementById("btn-export-html").addEventListener("click", () => downloadReport("html"));

  async function downloadReport(format) {
    try {
      const data = await api("/api/report", {
        method: "POST",
        body: JSON.stringify({ format }),
      });
      const blob = new Blob([data.content], { type: data.mimetype });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `AI-2026-0042-forensic-report.${format === "markdown" ? "md" : "html"}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("Export failed: " + e.message);
    }
  }

  // -------------------------------------------------------------------
  // Presentation mode
  // -------------------------------------------------------------------
  document.getElementById("btn-presentation").addEventListener("click", () => {
    document.body.classList.toggle("presentation");
  });

  // -------------------------------------------------------------------
  // Guided investigation
  // -------------------------------------------------------------------
  async function loadGuidedSteps() {
    const data = await api("/api/guided-steps");
    state.guidedSteps = data.steps;
  }

  document.getElementById("btn-guided").addEventListener("click", () => {
    state.guidedActive = true;
    state.guidedIndex = 0;
    document.getElementById("guided-overlay").classList.remove("hidden");
    renderGuidedStep();
  });
  document.getElementById("guided-exit").addEventListener("click", () => {
    document.getElementById("guided-overlay").classList.add("hidden");
  });
  document.getElementById("guided-prev").addEventListener("click", () => {
    if (state.guidedIndex > 0) {
      state.guidedIndex -= 1;
      renderGuidedStep();
    }
  });
  document.getElementById("guided-next").addEventListener("click", () => {
    if (state.guidedIndex < state.guidedSteps.length - 1) {
      state.guidedIndex += 1;
      renderGuidedStep();
    } else {
      document.getElementById("guided-overlay").classList.add("hidden");
      document.getElementById("final-overlay").classList.remove("hidden");
    }
  });
  document.getElementById("final-close").addEventListener("click", () => {
    document.getElementById("final-overlay").classList.add("hidden");
  });

  function renderGuidedStep() {
    const step = state.guidedSteps[state.guidedIndex];
    if (!step) return;
    document.getElementById("guided-step-num").textContent = step.step;
    document.getElementById("guided-step-title").textContent = step.title;
    document.getElementById("guided-step-question").textContent = step.question;
    const reveal = document.getElementById("guided-reveal");
    if (step.reveal) {
      reveal.textContent = step.reveal;
      reveal.classList.remove("hidden");
    } else {
      reveal.classList.add("hidden");
    }
    document.getElementById("guided-prev").disabled = state.guidedIndex === 0;
    document.getElementById("guided-next").textContent =
      state.guidedIndex === state.guidedSteps.length - 1 ? "Finish" : "Next";

    if (step.focus) {
      switchStage(step.focus.stage);
      document.querySelectorAll(".stage-tab").forEach((t) => t.classList.toggle("active", t.dataset.stage === step.focus.stage));
      if (step.focus.evidence_id) {
        setTimeout(() => openEvidenceModal(step.focus.evidence_id), 50);
      }
    }
  }

  // -------------------------------------------------------------------
  // Init
  // -------------------------------------------------------------------
  async function init() {
    await loadCategories();
    await Promise.all([
      loadEvidence(),
      loadTrace(),
      loadTimeline(),
      loadCustody(),
      loadEvidenceMap(),
      loadFindings(),
      loadRootCause(),
      loadGuidedSteps(),
      loadOllamaStatus(),
    ]);
  }

  init();
})();
