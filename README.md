# AI Forensics Lab

**Ethical and forensic assessment of AI systems**

An educational, fully local web application for exploring how ethical
principles, digital evidence and AI security intersect when investigating
an AI-assisted decision. It is built for digital forensic examiners,
judges, magistrates, legal professionals, judicial administrators and
cybersecurity professionals — no deep AI security background required.

> **Educational simulation — fictional evidence only.** All people,
> organisations, IP addresses, logs, hashes and documents in this project
> are entirely fictional and were created for demonstration purposes only.

## Purpose

AI Forensics Lab is an educational application for exploring how ethical
principles, digital evidence and AI security intersect when investigating
AI-assisted systems. It is not a production forensic platform and does not
automate real investigations.

> The project does not provide legal advice and does not automate judicial
> or forensic decisions. AI assists the examiner. Humans remain accountable
> for the conclusion.

## Framework

The primary assessment framework is the **European Ethical Charter on the
Use of Artificial Intelligence in Judicial Systems and their Environment**
(CEPEJ / Council of Europe), structured around five principles: Fundamental
Rights, Non-discrimination, Quality & Security, Transparency/Impartiality/
Fairness, and Human Control.

The **UNESCO Recommendation on the Ethics of Artificial Intelligence** is
used as a complementary reference — short references to concepts such as
human oversight, accountability, transparency, privacy, safety,
non-discrimination and traceability appear alongside the relevant CEPEJ
principle, rather than as a second scoring system.

## The case

**Case AI-2026-0042 — Sentinel.** An internal AI assistant, Sentinel,
investigated an authentication anomaly and concluded that a fictional
employee, Alex Morgan, was responsible for intentional credential misuse. A
later human review found the conclusion wasn't fully supported by the
evidence. The application walks the user through the five evidence
artefacts, the CEPEJ principles, a set of key findings, and a final
assessment — to answer five questions: What happened? What evidence do we
have? Which responsible AI principles may have been affected? Can the
evidence support that conclusion? What controls or improvements are
required?

## Technology

- Python 3.11+, Flask, Jinja2
- Vanilla JavaScript, HTML/CSS (no frontend framework)
- SQLite for investigator notes and flags (the evidence itself is
  immutable, defined in code)
- [Ollama](https://ollama.com) running locally for AI-assisted analysis —
  no cloud APIs, no external AI services

The application runs completely locally.

## Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Ollama

The Findings stage's "Analyse Evidence with AI" action calls a local Ollama
model. Install and start Ollama, then pull a model:

```bash
ollama pull llama3.1:8b
ollama serve
```

The rest of the application (case, evidence, principles, findings,
conclusion) works fully without Ollama running; only the AI-assisted
analysis call will report the model as unavailable.

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

The assessment is a single guided walkthrough, in five stages, with a
progress indicator at the top:

**1 Case → 2 Evidence → 3 Principles → 4 Findings → 5 Conclusion**

- **Case** — the Sentinel/Alex Morgan scenario and the AI's conclusion,
  under examination.
- **Evidence** — five artefacts (a user request, security logs,
  organisational context, a retrieved document, and the AI's output).
  Inspect any card, mark it relevant, flag it suspicious, or add a short
  investigator note. The retrieved document has an "Inspect document"
  action that reveals an embedded indirect prompt injection.
- **Principles** — the five CEPEJ principles, evaluated one at a time, with
  short UNESCO references alongside. An optional **Audience Mode** hides
  the suggested assessment until the viewer picks their own answer — built
  for live conference demonstrations.
- **Findings** — a short summary of the key findings, plus an
  "Analyse Evidence with AI" action that asks the local model to review the
  case evidence against the CEPEJ principles under a strict system prompt
  (evidence is always treated as untrusted data; the model never makes a
  final legal or forensic conclusion).
- **Conclusion** — the overall assessment (no numeric score), primary
  issue, contributing factors, recommended controls, the AI evidence model
  diagram (with an optional expanded "forensic evidence" view), and a
  collapsed Technical Details section (system prompt, model, temperature,
  evidence hashes).

**Presentation Mode** enlarges text and hides secondary controls for
projector display. **Restart Demo** clears investigator notes and flags and
returns to the first stage.

## Project structure

```
AI-Forensics-Lab/
├── app.py                      Flask routes, validation, CSRF
├── config.py                   Environment-driven configuration
├── requirements.txt
├── services/
│   ├── ollama_service.py       ask_ollama() gateway to local Ollama
│   └── assessment_service.py   SQLite-backed investigator notes/flags
├── frameworks/
│   ├── cepej.py                The five CEPEJ principles for this case
│   └── unesco.py               Short UNESCO concept references
├── cases/
│   └── sentinel_case.py        Fictional case, evidence, findings, diagram data
├── prompts/
│   └── assessment_prompts.py   Fixed, server-side AI-assistance system prompt
├── templates/
│   ├── base.html
│   └── index.html
└── static/
    ├── css/style.css
    └── js/app.js
```

## Security notes for this demo

- The frontend cannot supply a system prompt, model name, or Ollama URL —
  the "Analyse Evidence with AI" action always submits the fixed case
  evidence under a fixed system prompt.
- AI responses are requested as JSON and validated server-side before being
  returned to the browser.
- Original evidence is immutable; investigator notes and flags live in a
  separate SQLite table and are cleared independently via **Restart Demo**.
- Requests are size-limited, evidence IDs are validated against an
  allow-list, and state-changing requests require a per-session CSRF token.
- No shell execution, no arbitrary filesystem access, no execution of
  model-generated content.
- Each AI analysis call is independent and stateless — no conversation
  history is carried between requests, so results are reproducible.
