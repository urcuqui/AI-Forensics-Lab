"""Short, secondary reference material from the UNESCO Recommendation on the
Ethics of Artificial Intelligence (2021).

This is intentionally not a second full assessment framework. It only
supplies short, plain-language descriptions of internationally recognised
AI ethics concepts that the interface links to from relevant CEPEJ
principle cards (see frameworks/cepej.py).
"""

RELATIONSHIP_NOTE = (
    "CEPEJ provides the justice-specific assessment lens used in this "
    "walkthrough, while UNESCO provides broader, internationally "
    "recognised principles for responsible AI. UNESCO references appear "
    "here as short supporting context, not as a second scoring system."
)

CONCEPTS = {
    "human_oversight": {
        "label": "Human oversight",
        "description": "AI systems should not displace ultimate human "
                        "responsibility and accountability for decisions "
                        "that affect people.",
    },
    "accountability": {
        "label": "Accountability",
        "description": "Someone must remain answerable for the outcomes of "
                        "an AI-assisted decision, including when the AI "
                        "system behaves unexpectedly.",
    },
    "transparency": {
        "label": "Transparency",
        "description": "It should be possible to explain, in appropriate "
                        "terms, how and why an AI system reached a given "
                        "output.",
    },
    "privacy": {
        "label": "Privacy",
        "description": "Personal data used or produced by an AI system "
                        "should be protected throughout its lifecycle.",
    },
    "safety": {
        "label": "Safety & security",
        "description": "AI systems should be robust and secure against "
                        "manipulation, and should avoid unintended harm.",
    },
    "non_discrimination": {
        "label": "Non-discrimination",
        "description": "AI systems should avoid introducing or amplifying "
                        "bias against individuals or groups.",
    },
    "traceability": {
        "label": "Traceability",
        "description": "The data, process and reasoning behind an AI "
                        "system's output should be documented well enough "
                        "to be reviewed later.",
    },
}
