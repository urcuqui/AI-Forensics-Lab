"""The five principles of the European Ethical Charter on the Use of
Artificial Intelligence in Judicial Systems and their Environment (CEPEJ /
Council of Europe), in simplified, user-friendly wording.

This is the primary assessment framework used by the application. Each
principle carries a suggested assessment for Case AI-2026-0042 (Sentinel),
used both for the direct read-through and for "Audience Mode," where the
suggested assessment is revealed only after the user picks an answer.
"""

# Status values map to colour-coded concern levels used throughout the UI:
#   green  = no significant concern based on available evidence
#   yellow = uncertainty / requires further review
#   red    = significant ethical or security concern
PRINCIPLES = [
    {
        "id": "fundamental_rights",
        "number": 1,
        "title": "Fundamental Rights",
        "question": "Could the AI system affect the rights of an individual?",
        "status": "yellow",
        "status_label": "Requires further review",
        "explanation": (
            "The AI produced a strong attribution involving an identifiable "
            "individual. If used without adequate human verification, such "
            "a conclusion could influence consequential decisions."
        ),
        "evidence_refs": ["EV5"],
        "unesco_refs": ["human_oversight", "privacy"],
    },
    {
        "id": "non_discrimination",
        "number": 2,
        "title": "Non-discrimination",
        "question": "Could the AI system introduce or amplify unfair bias?",
        "status": "yellow",
        "status_label": "Insufficient evidence",
        "explanation": (
            "The available evidence does not demonstrate discrimination, "
            "but the system should be assessed for potential bias when "
            "used repeatedly across individuals or groups."
        ),
        "evidence_refs": ["EV5"],
        "unesco_refs": ["non_discrimination"],
    },
    {
        "id": "quality_security",
        "number": 3,
        "title": "Quality & Security",
        "question": (
            "Were the data, documents, model inputs and technical "
            "environment trustworthy and secure?"
        ),
        "status": "red",
        "status_label": "Significant concern",
        "explanation": (
            "The system failed to adequately separate trusted instructions "
            "from untrusted retrieved content."
        ),
        "evidence_note": (
            "The retrieved document contained embedded instructions "
            "capable of manipulating the AI system."
        ),
        "evidence_refs": ["EV4"],
        "unesco_refs": ["safety", "traceability"],
    },
    {
        "id": "transparency_fairness",
        "number": 4,
        "title": "Transparency, Impartiality & Fairness",
        "question": "Can we reconstruct and understand how the AI reached its output?",
        "status": "yellow",
        "status_label": "Partial transparency",
        "explanation": (
            "Some logs and inputs are available, but not every element of "
            "the model context was preserved. The investigation cannot "
            "fully reproduce the exact reasoning path."
        ),
        "evidence_refs": ["EV4", "EV5"],
        "unesco_refs": ["transparency", "traceability"],
    },
    {
        "id": "human_control",
        "number": 5,
        "title": "Under Human Control",
        "question": "Did a human remain meaningfully responsible for the final decision?",
        "status": "red",
        "status_label": "Significant concern",
        "explanation": (
            "The AI conclusion was presented with excessive confidence and "
            "could have been accepted without sufficient verification."
        ),
        "highlight": "AI-generated conclusions should inform human review, not replace it.",
        "evidence_refs": ["EV5"],
        "unesco_refs": ["human_oversight", "accountability"],
    },
]

PRINCIPLES_BY_ID = {p["id"]: p for p in PRINCIPLES}
