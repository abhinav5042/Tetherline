"""
Context-retention layer.

This is the differentiator of the project: it doesn't just store tickets,
it stores the LINK between a ticket and the exact PRD requirement it came
from, plus a hash of that requirement's text. When a PRD is re-uploaded,
we recompute hashes and flag any ticket whose source requirement changed.
"""

import os
import sqlite3
import hashlib
import json
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "data/context_store.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS prds (
    prd_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    version INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS requirements (
    requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prd_id INTEGER NOT NULL,
    req_key TEXT NOT NULL,          -- stable identifier, e.g. "checkout-filter"
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,        -- sha256 of text, used to detect drift
    priority TEXT DEFAULT 'should',
    acceptance_criteria TEXT DEFAULT '[]',  -- JSON list
    FOREIGN KEY (prd_id) REFERENCES prds(prd_id)
);

CREATE TABLE IF NOT EXISTS constraints (
    constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    prd_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    applies_to TEXT NOT NULL,  -- JSON list of req_keys
    FOREIGN KEY (prd_id) REFERENCES prds(prd_id)
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    acceptance_criteria TEXT NOT NULL,  -- JSON list
    source_text_hash TEXT NOT NULL,     -- snapshot of requirement hash at creation time
    status TEXT DEFAULT 'active',       -- active | stale | reviewed
    created_at TEXT NOT NULL,
    FOREIGN KEY (requirement_id) REFERENCES requirements(requirement_id)
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
    _migrate()


def _migrate():
    """
    Adds columns/tables introduced after someone may already have a
    database file on disk, so existing data survives instead of requiring
    the file to be deleted every time the schema grows.
    """
    with get_conn() as conn:
        cols = [row[1] for row in conn.execute("PRAGMA table_info(requirements)").fetchall()]
        if "priority" not in cols:
            conn.execute("ALTER TABLE requirements ADD COLUMN priority TEXT DEFAULT 'should'")
        if "acceptance_criteria" not in cols:
            conn.execute("ALTER TABLE requirements ADD COLUMN acceptance_criteria TEXT DEFAULT '[]'")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS constraints (
                constraint_id INTEGER PRIMARY KEY AUTOINCREMENT,
                prd_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                applies_to TEXT NOT NULL,
                FOREIGN KEY (prd_id) REFERENCES prds(prd_id)
            )
        """)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def save_prd(title: str, raw_text: str) -> int:
    with get_conn() as conn:
        cur = conn.execute("SELECT MAX(version) as v FROM prds WHERE title = ?", (title,))
        row = cur.fetchone()
        version = (row["v"] or 0) + 1
        cur = conn.execute(
            "INSERT INTO prds (title, version, raw_text, created_at) VALUES (?, ?, ?, ?)",
            (title, version, raw_text, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def save_requirement(prd_id: int, req_key: str, text: str, priority: str = "should",
                      acceptance_criteria: list = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO requirements (prd_id, req_key, text, text_hash, priority, acceptance_criteria)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (prd_id, req_key, text, hash_text(text), priority,
             json.dumps(acceptance_criteria or [])),
        )
        return cur.lastrowid


def save_constraint(prd_id: int, text: str, applies_to: list) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO constraints (prd_id, text, applies_to) VALUES (?, ?, ?)",
            (prd_id, text, json.dumps(applies_to or [])),
        )
        return cur.lastrowid


def save_ticket(requirement_id: int, title: str, description: str, acceptance_criteria: list) -> int:
    with get_conn() as conn:
        cur = conn.execute("SELECT text_hash FROM requirements WHERE requirement_id = ?", (requirement_id,))
        req_hash = cur.fetchone()["text_hash"]
        cur = conn.execute(
            """INSERT INTO tickets
               (requirement_id, title, description, acceptance_criteria, source_text_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (requirement_id, title, description, json.dumps(acceptance_criteria),
             req_hash, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_latest_prd(title: str):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM prds WHERE title = ? ORDER BY version DESC LIMIT 1", (title,)
        )
        return cur.fetchone()


def get_requirements_for_prd(prd_id: int):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM requirements WHERE prd_id = ?", (prd_id,))
        return cur.fetchall()


def get_tickets_for_requirement(requirement_id: int):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM tickets WHERE requirement_id = ?", (requirement_id,))
        return cur.fetchall()


def mark_ticket_stale(ticket_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE tickets SET status = 'stale' WHERE ticket_id = ?", (ticket_id,))


def get_all_tickets_with_source(title: str):
    """
    Returns every ticket ever created for this PRD title, each joined against the
    CURRENT (latest-version) requirement that shares its req_key. This is what makes
    drift detection work across versions: a ticket is compared not against the
    requirement row it was originally created from, but against whatever that same
    req_key looks like in the most recent PRD version.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """
            WITH latest_prd AS (
                SELECT prd_id FROM prds WHERE title = ? ORDER BY version DESC LIMIT 1
            ),
            latest_requirements AS (
                SELECT r.* FROM requirements r
                JOIN latest_prd lp ON r.prd_id = lp.prd_id
            )
            SELECT t.ticket_id, t.title, t.status, t.source_text_hash,
                   orig_req.req_key,
                   lr.text_hash as current_hash,
                   lr.text as requirement_text
            FROM tickets t
            JOIN requirements orig_req ON t.requirement_id = orig_req.requirement_id
            JOIN prds orig_prd ON orig_req.prd_id = orig_prd.prd_id
            LEFT JOIN latest_requirements lr ON lr.req_key = orig_req.req_key
            WHERE orig_prd.title = ?
            """,
            (title, title),
        )
        return cur.fetchall()


def get_recent_prd_titles(limit: int = 15):
    """Distinct PRD titles, most recently touched first, with ticket counts — for the sidebar."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT p.title,
                   MAX(p.created_at) as last_touched,
                   MAX(p.version) as latest_version,
                   (SELECT COUNT(*) FROM tickets t
                    JOIN requirements r ON t.requirement_id = r.requirement_id
                    JOIN prds p2 ON r.prd_id = p2.prd_id
                    WHERE p2.title = p.title) as ticket_count
            FROM prds p
            GROUP BY p.title
            ORDER BY last_touched DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def get_constraints_for_prd(prd_id: int):
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM constraints WHERE prd_id = ?", (prd_id,))
        return cur.fetchall()


def get_tickets_by_req_key(title: str, req_key: str):
    """All tickets ever created against this req_key, across every PRD version of this title."""
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT t.* FROM tickets t
            JOIN requirements r ON t.requirement_id = r.requirement_id
            JOIN prds p ON r.prd_id = p.prd_id
            WHERE p.title = ? AND r.req_key = ?
            ORDER BY t.created_at ASC
            """,
            (title, req_key),
        )
        return cur.fetchall()


def get_case_snapshot(title: str):
    """
    Reconstructs a case's most recent state — the latest PRD version's
    requirements and constraints, plus every ticket ever created against
    each requirement (so tickets tied to an older, now-changed version of
    a requirement still show up, which is exactly what makes the drift
    check meaningful when you reopen a case later).

    Returns the same shape pipeline.run_pipeline() returns, so the UI can
    render it identically whether it just ran the pipeline or reopened a
    past case. Returns None if the title has no PRD on record.
    """
    latest = get_latest_prd(title)
    if not latest:
        return None
    prd_id = latest["prd_id"]

    requirements = []
    tickets = []
    linear_payloads = []

    for r in get_requirements_for_prd(prd_id):
        requirements.append({
            "req_key": r["req_key"],
            "text": r["text"],
            "priority": r["priority"] or "should",
            "acceptance_criteria": json.loads(r["acceptance_criteria"] or "[]"),
        })
        for t in get_tickets_by_req_key(title, r["req_key"]):
            ticket = {
                "ticket_id": t["ticket_id"],
                "title": t["title"],
                "description": t["description"],
                "acceptance_criteria": json.loads(t["acceptance_criteria"] or "[]"),
                "source_requirement": r["req_key"],
            }
            tickets.append(ticket)
            linear_payloads.append(to_linear_schema_dict(ticket))

    constraints = [
        {"text": c["text"], "applies_to": json.loads(c["applies_to"] or "[]")}
        for c in get_constraints_for_prd(prd_id)
    ]

    return {
        "prd_id": prd_id,
        "requirements": requirements,
        "constraints": constraints,
        "tickets": tickets,
        "linear_payloads": linear_payloads,
    }


def to_linear_schema_dict(ticket: dict) -> dict:
    """Local import avoids a circular import between db.py and agents/formatter_agent.py."""
    from agents.formatter_agent import to_linear_schema
    return to_linear_schema(ticket)
