"""AI Forensics Lab - educational Flask application.

Guides a non-technical investigator through a fictional AI-related incident
(Case AI-2026-0042 - Sentinel) in five stages: Case, Evidence, Principles,
Findings, Conclusion. All evidence is fictional. This is a demonstration
tool, not a production forensic or legal platform.
"""
import logging
import secrets

from flask import Flask, jsonify, render_template, request, session, abort

import config
from cases import sentinel_case as case_data
from frameworks import cepej, unesco
from prompts import assessment_prompts
from services import assessment_service, ollama_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

VALID_EVIDENCE_IDS = set(case_data.EVIDENCE_BY_ID.keys())

STATUS_EMOJI = {"red": "\U0001F534", "yellow": "\U0001F7E1", "green": "\U0001F7E2"}


with app.app_context():
    assessment_service.init_db()


# ---------------------------------------------------------------------------
# CSRF protection (lightweight, session-token based - no external deps)
# ---------------------------------------------------------------------------

@app.before_request
def _ensure_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


def _check_csrf():
    token = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    if not token or not secrets.compare_digest(token, expected):
        abort(403, description="Invalid or missing CSRF token.")


@app.after_request
def _security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


def _json_error(message, status=400):
    return jsonify({"error": message}), status


@app.errorhandler(403)
def _forbidden(e):
    return _json_error(str(e.description) if hasattr(e, "description") else "Forbidden", 403)


@app.errorhandler(413)
def _too_large(e):
    return _json_error("Request too large.", 413)


@app.errorhandler(404)
def _not_found(e):
    return _json_error("Not found.", 404)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_evidence_id(evidence_id):
    if evidence_id not in VALID_EVIDENCE_IDS:
        abort(400, description=f"Unknown evidence id: {evidence_id}")
    return evidence_id


def _clean_text(value, max_len, field_name):
    if not isinstance(value, str):
        abort(400, description=f"{field_name} must be a string.")
    value = value.strip()
    if not value:
        abort(400, description=f"{field_name} must not be empty.")
    if len(value) > max_len:
        abort(400, description=f"{field_name} exceeds maximum length of {max_len}.")
    return value


def _get_json_body():
    if not request.is_json:
        abort(400, description="Request body must be JSON.")
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        abort(400, description="Invalid JSON body.")
    return body


# ---------------------------------------------------------------------------
# Page route - single guided page, all reference content rendered server-side
# ---------------------------------------------------------------------------

def _public_evidence(e):
    flag = assessment_service.get_flag(e["id"]) or {}
    notes = assessment_service.get_notes(e["id"])
    public = dict(e)
    public["flagged"] = bool(flag.get("flagged", 0))
    public["relevant"] = bool(flag.get("relevant", 0))
    public["notes"] = notes
    return public


@app.route("/")
def index():
    return render_template(
        "index.html",
        case=case_data.CASE,
        incident_summary=case_data.INCIDENT_SUMMARY,
        core_messages=case_data.CORE_MESSAGES,
        evidence=[_public_evidence(e) for e in case_data.EVIDENCE],
        principles=cepej.PRINCIPLES,
        unesco_concepts=unesco.CONCEPTS,
        unesco_relationship=unesco.RELATIONSHIP_NOTE,
        findings=case_data.FINDINGS,
        evidence_model_simple=case_data.EVIDENCE_MODEL_SIMPLE,
        evidence_model_expanded=case_data.EVIDENCE_MODEL_EXPANDED,
        final_assessment=case_data.FINAL_ASSESSMENT,
        system_prompt=assessment_prompts.ASSESSMENT_SYSTEM_PROMPT,
        config=config,
        status_emoji=STATUS_EMOJI,
        csrf_token=session["csrf_token"],
    )


# ---------------------------------------------------------------------------
# Evidence API (notes + flags only - the underlying evidence is immutable)
# ---------------------------------------------------------------------------

@app.route("/api/evidence/<evidence_id>")
def api_evidence_detail(evidence_id):
    _validate_evidence_id(evidence_id)
    return jsonify(_public_evidence(case_data.EVIDENCE_BY_ID[evidence_id]))


@app.route("/api/evidence/<evidence_id>/note", methods=["POST"])
def api_add_note(evidence_id):
    _check_csrf()
    _validate_evidence_id(evidence_id)
    body = _get_json_body()
    note_text = _clean_text(body.get("note", ""), config.MAX_NOTE_LENGTH, "note")
    assessment_service.add_note(evidence_id, note_text)
    return jsonify(_public_evidence(case_data.EVIDENCE_BY_ID[evidence_id]))


@app.route("/api/evidence/<evidence_id>/flag", methods=["POST"])
def api_flag_evidence(evidence_id):
    _check_csrf()
    _validate_evidence_id(evidence_id)
    body = _get_json_body()
    flagged = body.get("flagged")
    relevant = body.get("relevant")
    if flagged is not None and not isinstance(flagged, bool):
        abort(400, description="flagged must be boolean.")
    if relevant is not None and not isinstance(relevant, bool):
        abort(400, description="relevant must be boolean.")
    assessment_service.set_flag(evidence_id, flagged=flagged, relevant=relevant)
    return jsonify(_public_evidence(case_data.EVIDENCE_BY_ID[evidence_id]))


@app.route("/api/ollama-status")
def api_ollama_status():
    ok, message = ollama_service.check_connection()
    return jsonify({"connected": ok, "message": message, "model": config.OLLAMA_MODEL})


# ---------------------------------------------------------------------------
# AI-assisted analysis (Stage 4 - "Analyse Evidence with AI")
# ---------------------------------------------------------------------------

_ANALYSIS_LIST_FIELDS = [
    "observations", "potential_concerns", "affected_principles",
    "supporting_evidence", "missing_information", "alternative_explanations",
]


@app.route("/api/analyse", methods=["POST"])
def api_analyse():
    _check_csrf()

    messages = [
        {"role": "system", "content": assessment_prompts.ASSESSMENT_SYSTEM_PROMPT},
        {"role": "user", "content": assessment_prompts.build_user_message(case_data.EVIDENCE)},
    ]

    try:
        result = ollama_service.ask_ollama(messages)
    except ollama_service.OllamaError as exc:
        return _json_error(str(exc), 502)

    validated = _validate_analysis_schema(result)
    if validated is None:
        return _json_error("Model response did not match the expected schema.", 502)

    return jsonify(validated)


def _validate_analysis_schema(result):
    if not isinstance(result, dict):
        return None
    out = {}
    for field in _ANALYSIS_LIST_FIELDS:
        value = result.get(field, [])
        if not isinstance(value, list):
            return None
        out[field] = [str(v) for v in value][:50]
    return out


# ---------------------------------------------------------------------------
# Reset (demo convenience - clears investigator-created data only)
# ---------------------------------------------------------------------------

@app.route("/api/reset", methods=["POST"])
def api_reset():
    _check_csrf()
    assessment_service.reset_all()
    return jsonify({"status": "reset", "message": "Investigator notes and flags cleared. "
                                                    "Original evidence is immutable and unaffected."})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
