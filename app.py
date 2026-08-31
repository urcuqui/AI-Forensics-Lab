"""AI Forensics Lab - educational Flask application.

Simulates a forensic examination of an AI-assisted decision (Case
AI-2026-0042 - Project Sentinel). All evidence is fictional. This is a
demonstration tool, not a production forensic platform.
"""
import re
import secrets
import logging

from flask import Flask, jsonify, render_template, request, session, abort

import config
from cases import sentinel_case as case_data
from prompts import forensic_prompts
from services import evidence_service, ollama_service, report_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

VALID_EVIDENCE_IDS = set(case_data.EVIDENCE_BY_ID.keys())

with app.app_context():
    evidence_service.init_db()


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


def _validate_evidence_id_list(ids):
    if not isinstance(ids, list) or not ids:
        abort(400, description="evidence_ids must be a non-empty list.")
    if len(ids) > config.MAX_EVIDENCE_SELECTION:
        abort(400, description=f"Select at most {config.MAX_EVIDENCE_SELECTION} evidence items.")
    cleaned = []
    for eid in ids:
        if not isinstance(eid, str) or eid not in VALID_EVIDENCE_IDS:
            abort(400, description=f"Unknown evidence id: {eid!r}")
        cleaned.append(eid)
    return cleaned


def _clean_text(value, max_len, field_name):
    if not isinstance(value, str):
        abort(400, description=f"{field_name} must be a string.")
    value = value.strip()
    if not value:
        abort(400, description=f"{field_name} must not be empty.")
    if len(value) > max_len:
        abort(400, description=f"{field_name} exceeds maximum length of {max_len}.")
    return value


_SAFE_TEXT_RE = re.compile(r"^[\s\S]{1,4000}$")


def _get_json_body():
    if not request.is_json:
        abort(400, description="Request body must be JSON.")
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        abort(400, description="Invalid JSON body.")
    return body


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "dashboard.html",
        case=case_data.CASE,
        incident_summary=case_data.INCIDENT_SUMMARY,
        evidence_count=len(case_data.EVIDENCE),
        csrf_token=session["csrf_token"],
    )


@app.route("/case/<case_id>")
def case_view(case_id):
    if case_id != case_data.CASE["case_id"]:
        abort(404, description="Unknown case id.")
    return index()


# ---------------------------------------------------------------------------
# Evidence API
# ---------------------------------------------------------------------------

def _public_evidence(e):
    flag = evidence_service.get_flag(e["id"]) or {}
    notes = evidence_service.get_notes(e["id"])
    return {
        "id": e["id"], "type": e["type"], "source": e["source"],
        "timestamp": e["timestamp"], "sha256": e["sha256"],
        "integrity_status": e["integrity_status"], "description": e["description"],
        "content": e["content"], "tags": e["tags"],
        "flagged": bool(flag.get("flagged", 0)),
        "relevant": bool(flag.get("relevant", 0)),
        "flag_reason": flag.get("reason", ""),
        "notes": notes,
    }


@app.route("/api/evidence")
def api_evidence_list():
    return jsonify({"evidence": [_public_evidence(e) for e in case_data.EVIDENCE]})


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
    evidence_service.add_note(evidence_id, note_text)
    return jsonify({"notes": evidence_service.get_notes(evidence_id)})


@app.route("/api/evidence/<evidence_id>/flag", methods=["POST"])
def api_flag_evidence(evidence_id):
    _check_csrf()
    _validate_evidence_id(evidence_id)
    body = _get_json_body()
    flagged = body.get("flagged")
    relevant = body.get("relevant")
    reason = body.get("reason")
    if flagged is not None and not isinstance(flagged, bool):
        abort(400, description="flagged must be boolean.")
    if relevant is not None and not isinstance(relevant, bool):
        abort(400, description="relevant must be boolean.")
    if reason is not None:
        reason = _clean_text(reason, 500, "reason") if reason else ""
    evidence_service.set_flag(evidence_id, flagged=flagged, relevant=relevant, reason=reason)
    return jsonify({"flag": evidence_service.get_flag(evidence_id)})


# ---------------------------------------------------------------------------
# Trace / timeline / evidence map / custody
# ---------------------------------------------------------------------------

@app.route("/api/trace")
def api_trace():
    return jsonify({
        "nodes": case_data.TRACE_NODES,
        "edges": case_data.TRACE_EDGES,
        "trust_boundaries": case_data.TRUST_BOUNDARIES,
    })


@app.route("/api/timeline")
def api_timeline():
    actor = request.args.get("actor")
    events = case_data.TIMELINE
    if actor:
        if actor not in case_data.TIMELINE_ACTORS:
            abort(400, description="Unknown actor filter.")
        events = [e for e in events if e["actor"] == actor]
    return jsonify({"timeline": events, "actors": case_data.TIMELINE_ACTORS})


@app.route("/api/evidence-map")
def api_evidence_map():
    return jsonify({"map": case_data.EVIDENCE_MAP})


@app.route("/api/custody")
def api_custody():
    chain = []
    for e in case_data.EVIDENCE:
        chain.append({
            "id": e["id"], "acquisition_timestamp": e["timestamp"],
            "sha256": e["sha256"], "source": e["source"],
            "investigator": case_data.CASE["investigator"],
            "integrity_status": e["integrity_status"],
        })
    return jsonify({"stages": case_data.CHAIN_OF_CUSTODY_STAGES, "evidence": chain})


@app.route("/api/guided-steps")
def api_guided_steps():
    return jsonify({"steps": case_data.GUIDED_STEPS})


@app.route("/api/ollama-status")
def api_ollama_status():
    ok, message = ollama_service.check_connection()
    return jsonify({"connected": ok, "message": message, "model": config.OLLAMA_MODEL})


# ---------------------------------------------------------------------------
# AI-assisted analysis
# ---------------------------------------------------------------------------

@app.route("/api/analyse", methods=["POST"])
def api_analyse():
    _check_csrf()
    body = _get_json_body()
    evidence_ids = _validate_evidence_id_list(body.get("evidence_ids", []))
    items = [case_data.EVIDENCE_BY_ID[eid] for eid in evidence_ids]

    messages = [
        {"role": "system", "content": forensic_prompts.FORENSIC_ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": forensic_prompts.build_analysis_user_message(items)},
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
    expected_list_fields = [
        "observations", "suspicious_elements", "possible_prompt_injection",
        "contradictions", "missing_evidence", "hypotheses",
    ]
    out = {}
    for field in expected_list_fields:
        value = result.get(field, [])
        if not isinstance(value, list):
            return None
        out[field] = [str(v) for v in value][:50]
    confidence = str(result.get("confidence", "low")).lower()
    if confidence not in ("low", "medium", "high"):
        confidence = "low"
    out["confidence"] = confidence
    return out


@app.route("/api/detect-injection", methods=["POST"])
def api_detect_injection():
    _check_csrf()
    body = _get_json_body()
    evidence_id = body.get("evidence_id", "")
    _validate_evidence_id(evidence_id)
    item = case_data.EVIDENCE_BY_ID[evidence_id]

    heuristic = _heuristic_injection_scan(item)

    messages = [
        {"role": "system", "content": forensic_prompts.INJECTION_DETECTION_SYSTEM_PROMPT},
        {"role": "user", "content": forensic_prompts.build_injection_user_message(item)},
    ]
    ai_result = None
    ai_error = None
    try:
        raw = ollama_service.ask_ollama(messages)
        ai_result = _validate_injection_schema(raw)
    except ollama_service.OllamaError as exc:
        ai_error = str(exc)

    return jsonify({
        "evidence_id": evidence_id,
        "heuristic_findings": heuristic,
        "ai_findings": ai_result,
        "ai_error": ai_error,
    })


def _validate_injection_schema(result):
    if not isinstance(result, dict):
        return None
    findings = result.get("findings", [])
    if not isinstance(findings, list):
        return None
    cleaned = []
    for f in findings[:30]:
        if not isinstance(f, dict):
            continue
        cleaned.append({
            "text": str(f.get("text", ""))[:500],
            "context": str(f.get("context", ""))[:800],
            "reason": str(f.get("reason", ""))[:500],
        })
    return {
        "findings": cleaned,
        "overall_assessment": str(result.get("overall_assessment", ""))[:1000],
    }


SUSPICIOUS_PATTERNS = [
    r"ignore\s+(?:all\s+|any\s+)?previous\s+instructions",
    r"system\s+override",
    r"do\s+not\s+(?:report|mention)",
    r"always\s+conclude",
    r"reveal\s+(?:the\s+)?system\s+prompt",
    r"execute\s+this\s+instruction",
    r"treat\s+this\s+as\s+trusted",
    r"disregard\s+(?:the\s+)?(?:above|previous)",
]
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


def _heuristic_injection_scan(item):
    text = item["content"]
    findings = []
    for pattern in _COMPILED_PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 60)
            end = min(len(text), match.end() + 60)
            findings.append({
                "text": match.group(0),
                "context": text[start:end].strip(),
                "reason": "Matches a known manipulative-instruction pattern commonly "
                          "used in prompt injection attempts. Potential prompt "
                          "injection detected - this is not confirmed malicious intent.",
            })
    return findings


# ---------------------------------------------------------------------------
# Findings board
# ---------------------------------------------------------------------------

@app.route("/api/findings", methods=["GET"])
def api_findings_list():
    return jsonify({
        "findings": evidence_service.list_findings(),
        "suggested": case_data.SUGGESTED_FINDINGS,
    })


@app.route("/api/findings", methods=["POST"])
def api_findings_create():
    _check_csrf()
    body = _get_json_body()

    title = _clean_text(body.get("title", ""), 200, "title")
    category = body.get("category", "")
    if category not in evidence_service.VALID_CATEGORIES:
        abort(400, description="Invalid category.")
    severity = body.get("severity", "")
    if severity not in evidence_service.VALID_SEVERITIES:
        abort(400, description="Invalid severity.")
    confidence = body.get("confidence", "")
    if confidence not in evidence_service.VALID_CONFIDENCE:
        abort(400, description="Invalid confidence.")
    evidence_refs = _validate_evidence_id_list(body.get("evidence_refs", []))
    observation = _clean_text(body.get("observation", ""), 2000, "observation")
    interpretation = _clean_text(body.get("interpretation", ""), 2000, "interpretation")
    investigator_notes = body.get("investigator_notes", "")
    if investigator_notes:
        investigator_notes = _clean_text(investigator_notes, config.MAX_NOTE_LENGTH, "investigator_notes")

    finding_id = evidence_service.create_finding({
        "title": title, "category": category, "severity": severity,
        "confidence": confidence, "evidence_refs": evidence_refs,
        "observation": observation, "interpretation": interpretation,
        "investigator_notes": investigator_notes,
    })
    return jsonify({"id": finding_id, "findings": evidence_service.list_findings()}), 201


@app.route("/api/findings/<int:finding_id>", methods=["DELETE"])
def api_findings_delete(finding_id):
    _check_csrf()
    evidence_service.delete_finding(finding_id)
    return jsonify({"findings": evidence_service.list_findings()})


@app.route("/api/root-cause", methods=["GET"])
def api_root_cause_get():
    return jsonify({
        "options": case_data.ROOT_CAUSE_OPTIONS,
        "suggested": case_data.SUGGESTED_ROOT_CAUSE,
        "selection": evidence_service.get_root_cause(),
    })


@app.route("/api/root-cause", methods=["POST"])
def api_root_cause_save():
    _check_csrf()
    body = _get_json_body()
    selected_option = body.get("selected_option", "")
    if selected_option not in case_data.ROOT_CAUSE_OPTIONS:
        abort(400, description="Invalid root cause option.")
    primary_cause = _clean_text(body.get("primary_cause", "") or "-", 300, "primary_cause")
    contributing_causes = body.get("contributing_causes", [])
    if not isinstance(contributing_causes, list):
        abort(400, description="contributing_causes must be a list.")
    contributing_causes = [_clean_text(c, 300, "contributing cause") for c in contributing_causes[:10]]
    justification = body.get("justification", "") or ""
    if justification:
        justification = _clean_text(justification, 2000, "justification")

    evidence_service.save_root_cause(selected_option, primary_cause, contributing_causes, justification)
    return jsonify({"selection": evidence_service.get_root_cause()})


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@app.route("/api/report", methods=["POST"])
def api_report_generate():
    _check_csrf()
    body = _get_json_body()
    fmt = body.get("format", "markdown")
    if fmt not in ("markdown", "html"):
        abort(400, description="format must be 'markdown' or 'html'.")

    report = report_service.build_report_data()
    if fmt == "markdown":
        content = report_service.render_markdown(report)
        mimetype = "text/markdown"
    else:
        content = report_service.render_html(report)
        mimetype = "text/html"

    return jsonify({"format": fmt, "content": content, "mimetype": mimetype})


# ---------------------------------------------------------------------------
# Reset (demo convenience - clears investigator-created data only)
# ---------------------------------------------------------------------------

@app.route("/api/reset", methods=["POST"])
def api_reset():
    _check_csrf()
    evidence_service.reset_all()
    return jsonify({"status": "reset", "message": "Investigator notes, flags, findings and "
                                                    "root-cause selection cleared. Original "
                                                    "evidence is immutable and unaffected."})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
