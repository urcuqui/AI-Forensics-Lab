"""SQLite-backed storage for investigator work product.

Original evidence (cases/sentinel_case.py) is immutable and never touched by
this module. Everything here - notes and flags - is investigator-created
annotation, kept separate so the two are never confused.
"""
import os
import sqlite3
import time
from contextlib import contextmanager

import config


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
                updated_at REAL NOT NULL
            )
        """)


def reset_all():
    with _conn() as conn:
        conn.execute("DELETE FROM notes")
        conn.execute("DELETE FROM flags")


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

def set_flag(evidence_id, flagged=None, relevant=None):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT * FROM flags WHERE evidence_id = ?", (evidence_id,)
        ).fetchone()
        cur_flagged = existing["flagged"] if existing else 0
        cur_relevant = existing["relevant"] if existing else 0

        new_flagged = int(flagged) if flagged is not None else cur_flagged
        new_relevant = int(relevant) if relevant is not None else cur_relevant

        conn.execute(
            """INSERT INTO flags (evidence_id, flagged, relevant, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(evidence_id) DO UPDATE SET
                 flagged=excluded.flagged,
                 relevant=excluded.relevant,
                 updated_at=excluded.updated_at""",
            (evidence_id, new_flagged, new_relevant, time.time()),
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
