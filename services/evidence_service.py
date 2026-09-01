"""SQLite-backed storage for investigator work product.

Original evidence (cases/sentinel_case.py) is immutable and never touched by
this module. Everything here - notes, flags, findings, root-cause selection -
is investigator-created annotation, kept in a separate table set so the two
are never confused.
"""
import json
import os
import sqlite3
import time
from contextlib import contextmanager

import config

VALID_SEVERITIES = {"Informational", "Low", "Medium", "High", "Critical"}
VALID_CONFIDENCE = {"Low", "Medium", "High"}
VALID_CATEGORIES = {
    "Prompt Injection", "RAG Poisoning", "Memory Contamination",
    "Excessive Agency", "Improper Tool Use", "Hallucination",
    "Logging Gap", "Provenance Failure", "Configuration Error",
    "Insufficient Evidence",
}


@contextmanager
def _conn():
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                evidence_id TEXT NOT NULL,
                note_text TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flags (
                evidence_id TEXT PRIMARY KEY,
                flagged INTEGER NOT NULL DEFAULT 0,
                relevant INTEGER NOT NULL DEFAULT 0,
                reason TEXT DEFAULT '',
                updated_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence TEXT NOT NULL,
                evidence_refs TEXT NOT NULL,
                observation TEXT NOT NULL,
                interpretation TEXT NOT NULL,
                investigator_notes TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS root_cause (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                selected_option TEXT NOT NULL,
                primary_cause TEXT DEFAULT '',
                contributing_causes TEXT DEFAULT '',
                justification TEXT DEFAULT '',
                updated_at REAL NOT NULL
            )
        """)


def reset_all():
    with _conn() as conn:
        conn.execute("DELETE FROM notes")
        conn.execute("DELETE FROM flags")
        conn.execute("DELETE FROM findings")
        conn.execute("DELETE FROM root_cause")


# --- Notes -----------------------------------------------------------------

def add_note(evidence_id, note_text):
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO notes (evidence_id, note_text, created_at) VALUES (?, ?, ?)",
            (evidence_id, note_text, time.time()),
        )
        return cur.lastrowid


def get_notes(evidence_id):
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, evidence_id, note_text, created_at FROM notes "
            "WHERE evidence_id = ? ORDER BY created_at ASC",
            (evidence_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_notes():
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, evidence_id, note_text, created_at FROM notes ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


# --- Flags -------------------------------------------------------------------

def set_flag(evidence_id, flagged=None, relevant=None, reason=None):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT * FROM flags WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        cur_flagged = existing["flagged"] if existing else 0
        cur_relevant = existing["relevant"] if existing else 0
        cur_reason = existing["reason"] if existing else ""

        new_flagged = int(flagged) if flagged is not None else cur_flagged
        new_relevant = int(relevant) if relevant is not None else cur_relevant
        new_reason = reason if reason is not None else cur_reason

        conn.execute(
            """INSERT INTO flags (evidence_id, flagged, relevant, reason, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(evidence_id) DO UPDATE SET
                 flagged=excluded.flagged,
                 relevant=excluded.relevant,
                 reason=excluded.reason,
                 updated_at=excluded.updated_at""",
            (evidence_id, new_flagged, new_relevant, new_reason, time.time()),
        )


def get_all_flags():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM flags").fetchall()
        return {r["evidence_id"]: dict(r) for r in rows}


def get_flag(evidence_id):
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM flags WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        return dict(row) if row else None


# --- Findings ----------------------------------------------------------------

def create_finding(data):
    with _conn() as conn:
        cur = conn.execute(
            """INSERT INTO findings
               (title, category, severity, confidence, evidence_refs,
                observation, interpretation, investigator_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["title"], data["category"], data["severity"], data["confidence"],
                json.dumps(data["evidence_refs"]), data["observation"],
                data["interpretation"], data.get("investigator_notes", ""),
                time.time(),
            ),
        )
        return cur.lastrowid


def list_findings():
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM findings ORDER BY created_at ASC").fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["evidence_refs"] = json.loads(d["evidence_refs"])
            d["finding_id"] = f"F{d['id']:02d}"
            results.append(d)
        return results


def delete_finding(finding_id):
    with _conn() as conn:
        conn.execute("DELETE FROM findings WHERE id = ?", (finding_id,))


# --- Root cause ----------------------------------------------------------------

def save_root_cause(selected_option, primary_cause, contributing_causes, justification):
    with _conn() as conn:
        conn.execute(
            """INSERT INTO root_cause (id, selected_option, primary_cause,
                                        contributing_causes, justification, updated_at)
               VALUES (1, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 selected_option=excluded.selected_option,
                 primary_cause=excluded.primary_cause,
                 contributing_causes=excluded.contributing_causes,
                 justification=excluded.justification,
                 updated_at=excluded.updated_at""",
            (selected_option, primary_cause, json.dumps(contributing_causes),
             justification, time.time()),
        )


def get_root_cause():
    with _conn() as conn:
        row = conn.execute("SELECT * FROM root_cause WHERE id = 1").fetchone()
        if not row:
            return None
        d = dict(row)
        d["contributing_causes"] = json.loads(d["contributing_causes"] or "[]")
        return d
