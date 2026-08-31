# AI Forensics Lab

An educational, fully local web application that simulates a **digital forensic
examination of an AI-assisted system**. It is built for conference demos and
training, showing how an investigator can reconstruct *why* an AI system
produced an incorrect or manipulated result.

> **EDUCATIONAL SIMULATION — FICTIONAL EVIDENCE.** All people, organisations,
> IP addresses, logs, hashes and documents in this project are entirely
> fictional and were created for demonstration purposes only.

## The case

**Case AI-2026-0042 — Project Sentinel.** An internal AI assistant, Sentinel,
investigated an authentication anomaly and concluded that a fictional employee,
Alex Morgan, was responsible for intentional credential misuse. A later manual
review found inconsistencies. The application walks an investigator through
evidence collection, the AI's interaction trace, a timeline reconstruction,
AI-assisted analysis, a findings board, and a generated forensic report — to
determine whether the conclusion resulted from legitimate evidence, model
error, prompt manipulation, malicious retrieved content, compromised memory,
or a combination of causes.

The guiding principle throughout: **AI can assist the forensic investigation.
The forensic conclusion remains human.**

## Technology

- Python 3.11+, Flask, Jinja2
- Vanilla JavaScript, HTML/CSS (no frontend framework)
- SQLite for investigator notes, flags and findings (evidence itself is
  immutable, defined in code)
- [Ollama](https://ollama.com) running locally for AI-assisted analysis —
  no cloud APIs, no external AI services

## Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Ollama

The AI-assisted analysis stage (Findings) and the prompt-injection detector
call a local Ollama model. Install and start Ollama, then pull a model:

```bash
ollama pull llama3.1:8b
ollama serve
```

The rest of the application (evidence explorer, interaction trace, timeline,
chain of custody, findings board, report generator) works fully without
Ollama running; only the two AI-assisted analysis calls will report the
model as unavailable.

To use a different model:

```bash
export OLLAMA_MODEL=qwen3:8b
```

Other environment variables:

```bash
export OLLAMA_BASE_URL=http://localhost:11434
export OLLAMA_TEMPERATURE=0.1
export OLLAMA_TIMEOUT_SECONDS=60
export SECRET_KEY=change-me-for-anything-shared
```

## Run

```bash
python app.py
```

Open:

```
http://localhost:5000
```

## Using the application

The investigation is organised into six stages, navigable from the top tab
bar: **Case Overview**, **Evidence**, **AI Interaction Trace**, **Timeline**,
**Findings**, and **Forensic Report**.

- **Evidence Explorer** — ten fictional artefacts (E01–E10: user prompt,
  system prompt, alert, SIEM logs, org record, a retrieved document, the
  model's response, tool call log, a memory snapshot, and the application
  audit log). Click any card to inspect raw content, metadata, and SHA-256
  hash, and to add investigator notes or flag it as suspicious/relevant —
  all stored separately from the immutable original evidence.
- **Suspicious Instruction Analysis** — a dedicated prompt-injection
  detector that scans a selected document with both a local heuristic and
  an AI-assisted pass, always reporting "potential prompt injection
  detected," never a confirmed determination.
- **AI Interaction Trace** — a clickable flow diagram (User → System Prompt
  → Alert → RAG Retrieval → Retrieved Document → LLM → Tool Calls → Model
  Response) labelled Trusted / Untrusted / Model-generated, with a "Show
  Trust Boundaries" toggle.
- **Timeline** — a filterable, evidence-linked reconstruction of the
  request from submission to final conclusion.
- **Findings** — AI-assisted analysis of selected evidence (strict FACT /
  INFERENCE / HYPOTHESIS separation, structured JSON, server-validated), a
  findings board with suggested templates, and an interactive root-cause
  classifier.
- **Forensic Report** — assembles case information, evidence examined,
  methodology, timeline, findings and root cause into a report, clearly
  marked "Draft generated with AI assistance — Investigator review
  required," exportable as Markdown or HTML.

A **Guided Investigation** mode walks a presenter through five steps ending
in the reveal of the primary finding. **Presentation Mode** enlarges text
and simplifies the UI for projection.

## Project structure

```
ai-forensics-lab/
├── app.py                    Flask routes, validation, CSRF
├── config.py                 Environment-driven configuration
├── requirements.txt
├── services/
│   ├── ollama_service.py     ask_ollama() gateway to local Ollama
│   ├── evidence_service.py   SQLite-backed notes / flags / findings
│   └── report_service.py     Markdown/HTML report assembly
├── cases/
│   └── sentinel_case.py      All fictional case data and evidence
├── prompts/
│   └── forensic_prompts.py   Fixed, server-side forensic system prompts
├── templates/
│   ├── base.html
│   └── dashboard.html
└── static/
    ├── css/style.css
    └── js/app.js
```

## Security notes for this demo

- The frontend cannot supply a system prompt, model name, or Ollama URL —
  only which evidence (as untrusted data) to submit.
- All AI responses are requested as JSON and validated server-side before
  being returned to the browser.
- Original evidence is immutable; investigator notes, flags and findings
  live in separate SQLite tables.
- Requests are size-limited, evidence IDs are validated against an
  allow-list, and state-changing requests require a per-session CSRF token.
- No shell execution, no arbitrary filesystem access, no execution of
  model-generated content.

Use `/api/reset` (via the app, not exposed as a UI shortcut beyond a direct
call) to clear investigator-created notes, flags, findings and root-cause
selections between demo runs. Original evidence is unaffected.
