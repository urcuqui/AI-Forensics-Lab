"""Builds the forensic report (Markdown and HTML) from case data plus
whatever findings / root-cause selection the investigator has recorded.
Report generation is deterministic template assembly; any AI-drafted text
is clearly labelled and must be reviewed by the investigator.
"""
from datetime import datetime, timezone
from html import escape

from cases import sentinel_case as case_data
from services import evidence_service

AI_DISCLAIMER = (
    "Draft generated with AI assistance — Investigator review required. "
    "This section reflects observations and hypotheses; it does not constitute "
    "a final legal or disciplinary conclusion."
)


def _generated_timestamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def build_report_data():
    findings = evidence_service.list_findings()
    root_cause = evidence_service.get_root_cause()
    flags = evidence_service.get_all_flags()
    notes = evidence_service.get_all_notes()

    evidence_examined = []
    for e in case_data.EVIDENCE:
        flag = flags.get(e["id"])
        evidence_notes = [n for n in notes if n["evidence_id"] == e["id"]]
        evidence_examined.append({
            "id": e["id"], "type": e["type"], "source": e["source"],
            "timestamp": e["timestamp"], "sha256": e["sha256"],
            "integrity_status": e["integrity_status"],
            "flagged_suspicious": bool(flag and flag["flagged"]),
            "marked_relevant": bool(flag and flag["relevant"]),
            "note_count": len(evidence_notes),
        })

    return {
        "case": case_data.CASE,
        "incident_summary": case_data.INCIDENT_SUMMARY,
        "generated_at": _generated_timestamp(),
        "evidence_examined": evidence_examined,
        "timeline": case_data.TIMELINE,
        "findings": findings,
        "root_cause": root_cause,
        "root_cause_options": case_data.ROOT_CAUSE_OPTIONS,
    }


def render_markdown(report):
    c = report["case"]
    lines = []
    lines.append(f"# AI Incident Forensic Examination Report\n")
    lines.append(f"_{AI_DISCLAIMER}_\n")
    lines.append(f"Generated: {report['generated_at']}\n")

    lines.append("## 1. Case Information")
    lines.append(f"- Case ID: {c['case_id']}")
    lines.append(f"- Codename: {c['codename']}")
    lines.append(f"- Status: {c['status']}")
    lines.append(f"- Date opened: {c['date_opened']}")
    lines.append(f"- Investigator: {c['investigator']}")
    lines.append(f"- AI system involved: {c['ai_system']}")
    lines.append(f"- Model: {c['model']}")
    lines.append(f"- Organisation: {c['organisation']}\n")

    lines.append("## 2. Scope")
    lines.append(
        "This examination covers the AI system's inputs, retrieved content, tool "
        "invocations, memory state, and outputs associated with case ALT-421, in "
        "order to determine what caused Sentinel's conclusion regarding employee "
        "Alex Morgan.\n"
    )

    lines.append("## 3. Evidence Examined")
    lines.append("| ID | Type | Source | SHA-256 | Flagged | Relevant | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for e in report["evidence_examined"]:
        lines.append(
            f"| {e['id']} | {e['type']} | {e['source']} | `{e['sha256'][:16]}…` | "
            f"{'Yes' if e['flagged_suspicious'] else 'No'} | "
            f"{'Yes' if e['marked_relevant'] else 'No'} | {e['note_count']} |"
        )
    lines.append("")

    lines.append("## 4. Methodology")
    lines.append(
        "Evidence was collected from the application audit log, tool call log, "
        "and session memory buffer. Each artefact's integrity was verified via "
        "SHA-256 hash. The AI interaction trace was reconstructed to identify "
        "trust boundaries between user input, system instructions, retrieved "
        "content, tool output, and model output. A local LLM (via Ollama) was "
        "used as an analysis aid, under a fixed system prompt instructing it to "
        "treat all evidence as untrusted data and to separate fact, inference "
        "and hypothesis. All AI-assisted output was reviewed by the investigator.\n"
    )

    lines.append("## 5. Timeline")
    for t in report["timeline"]:
        lines.append(f"- {t['time']} — [{t['actor']}] {t['description']} (ref: {t['evidence_ref']})")
    lines.append("")

    lines.append("## 6. Technical Findings")
    if report["findings"]:
        for f in report["findings"]:
            lines.append(f"### {f['finding_id']} — {f['title']}")
            lines.append(f"- Category: {f['category']}")
            lines.append(f"- Severity: {f['severity']}")
            lines.append(f"- Confidence: {f['confidence']}")
            lines.append(f"- Evidence references: {', '.join(f['evidence_refs'])}")
            lines.append(f"- Observation: {f['observation']}")
            lines.append(f"- Interpretation: {f['interpretation']}")
            if f.get("investigator_notes"):
                lines.append(f"- Investigator notes: {f['investigator_notes']}")
            lines.append("")
    else:
        lines.append("No findings have been recorded yet.\n")

    lines.append("## 7. Root Cause Analysis")
    rc = report["root_cause"]
    if rc:
        lines.append(f"- Selected classification: **{rc['selected_option']}**")
        if rc.get("primary_cause"):
            lines.append(f"- Primary cause: {rc['primary_cause']}")
        if rc.get("contributing_causes"):
            lines.append(f"- Contributing causes: {', '.join(rc['contributing_causes'])}")
        if rc.get("justification"):
            lines.append(f"- Justification: {rc['justification']}")
    else:
        lines.append("No root cause classification has been recorded yet.")
    lines.append("")

    lines.append("## 8. Limitations")
    lines.append(
        "- The exact byte-for-byte context window sent to the model was not "
        "separately archived and was reconstructed from logs and evidence.\n"
        "- AI-assisted analysis in this report is a decision-support aid and may "
        "contain errors; it does not replace investigator judgement.\n"
        "- This case and all evidence herein are fictional and constructed for "
        "educational demonstration purposes.\n"
    )

    lines.append("## 9. Conclusions")
    lines.append(
        "Conclusions are limited to what the recorded findings and root-cause "
        "classification above support. " + AI_DISCLAIMER
    )
    lines.append("\n**Observation ≠ Interpretation ≠ Conclusion.**")
    lines.append("\n**Preserve. Reconstruct. Correlate. Verify.**")
    lines.append("\n_AI assists the forensic examiner. The forensic conclusion remains human._")

    return "\n".join(lines)


def render_html(report):
    md_based_body = render_markdown(report)
    # Minimal, safe HTML wrapper. We escape and lightly format rather than
    # running a full Markdown parser, to avoid pulling in untrusted deps.
    escaped = escape(md_based_body)
    html_lines = []
    for line in escaped.split("\n"):
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "":
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p>{line}</p>")

    body = "\n".join(html_lines)
    c = report["case"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>AI Incident Forensic Examination Report — {escape(c['case_id'])}</title>
<style>
body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; max-width: 900px;
        margin: 2rem auto; padding: 0 1.5rem; color: #1a2233; background: #f4f6f9; }}
h1, h2, h3 {{ color: #0d1b2a; }}
h2 {{ border-bottom: 2px solid #17a2b8; padding-bottom: 4px; margin-top: 2rem; }}
.banner {{ background: #0d1b2a; color: #fff; padding: 10px 16px; border-left: 4px solid #17a2b8;
           font-weight: 600; margin-bottom: 1.5rem; }}
li {{ margin-left: 1.2rem; }}
</style>
</head>
<body>
<div class="banner">EDUCATIONAL SIMULATION — FICTIONAL EVIDENCE</div>
{body}
</body>
</html>"""
