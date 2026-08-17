"""
Tests for db.py — the context-retention layer. These don't need OpenAI or
any network access, which is exactly why they're valuable: they lock in the
correctness of the drift-detection mechanism itself, independent of whether
the AI agents behave well on any given day.

Run with: pytest tests/test_db.py -v
"""

import os
import sys
import sqlite3
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db


@pytest.fixture
def temp_db(monkeypatch):
    """Points db.py at a fresh temp file for each test, so tests never touch your real data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setattr(db, "DB_PATH", tmp.name)
    db.init_db()
    yield
    os.unlink(tmp.name)


def test_hash_text_is_deterministic():
    assert db.hash_text("hello") == db.hash_text("hello")
    assert db.hash_text("hello") != db.hash_text("hello!")


def test_hash_text_ignores_surrounding_whitespace():
    assert db.hash_text("  hello  ") == db.hash_text("hello")


def test_save_and_retrieve_requirement(temp_db):
    prd_id = db.save_prd("Test Case", "raw prd text")
    req_id = db.save_requirement(
        prd_id, "checkout-filter", "Add a shipping filter.",
        priority="must", acceptance_criteria=["Shows 3 presets"]
    )
    reqs = db.get_requirements_for_prd(prd_id)
    assert len(reqs) == 1
    assert reqs[0]["req_key"] == "checkout-filter"
    assert reqs[0]["priority"] == "must"


def test_drift_not_flagged_when_requirement_unchanged(temp_db):
    prd_id = db.save_prd("Test Case", "v1 text")
    req_id = db.save_requirement(prd_id, "checkout-filter", "Add a shipping filter.")
    db.save_ticket(req_id, "Build filter UI", "desc", ["ac1"])

    stale = _find_stale(temp_db_title="Test Case")
    assert stale == []


def test_drift_flagged_when_requirement_text_changes(temp_db):
    prd_id = db.save_prd("Test Case", "v1 text")
    req_id = db.save_requirement(prd_id, "checkout-filter", "Add a shipping filter.")
    db.save_ticket(req_id, "Build filter UI", "desc", ["ac1"])

    # Simulate re-running the pipeline on an edited PRD: same req_key, new text
    prd_id_2 = db.save_prd("Test Case", "v2 text")
    db.save_requirement(prd_id_2, "checkout-filter", "Add a shipping AND cost filter.")

    stale = _find_stale(temp_db_title="Test Case")
    assert len(stale) == 1
    assert stale[0]["requirement_key"] == "checkout-filter"


def test_drift_not_flagged_for_unrelated_requirement(temp_db):
    """A ticket tied to req A shouldn't be flagged when only req B changes."""
    prd_id = db.save_prd("Test Case", "v1 text")
    req_a = db.save_requirement(prd_id, "req-a", "Requirement A text.")
    req_b = db.save_requirement(prd_id, "req-b", "Requirement B text.")
    db.save_ticket(req_a, "Ticket for A", "desc", ["ac1"])
    db.save_ticket(req_b, "Ticket for B", "desc", ["ac1"])

    prd_id_2 = db.save_prd("Test Case", "v2 text")
    db.save_requirement(prd_id_2, "req-a", "Requirement A text.")  # unchanged
    db.save_requirement(prd_id_2, "req-b", "Requirement B text CHANGED.")  # changed

    stale = _find_stale(temp_db_title="Test Case")
    assert len(stale) == 1
    assert stale[0]["requirement_key"] == "req-b"


def test_recent_prd_titles_ordered_most_recent_first(temp_db):
    prd_a = db.save_prd("Older Case", "text")
    req_a = db.save_requirement(prd_a, "req-a", "text")
    db.save_ticket(req_a, "t1", "d", ["ac"])

    prd_b = db.save_prd("Newer Case", "text")
    req_b = db.save_requirement(prd_b, "req-b", "text")
    db.save_ticket(req_b, "t2", "d", ["ac"])

    recents = db.get_recent_prd_titles()
    assert recents[0]["title"] == "Newer Case"
    assert recents[1]["title"] == "Older Case"


def test_case_snapshot_reconstructs_full_history(temp_db):
    prd_id = db.save_prd("Checkout Redesign", "raw text")
    req_id = db.save_requirement(
        prd_id, "checkout-filter", "Add filter.",
        priority="must", acceptance_criteria=["AC one"]
    )
    db.save_constraint(prd_id, "Must be encrypted", ["checkout-filter"])
    db.save_ticket(req_id, "Build filter UI", "desc", ["Ticket AC one"])

    snapshot = db.get_case_snapshot("Checkout Redesign")
    assert snapshot is not None
    assert len(snapshot["requirements"]) == 1
    assert snapshot["requirements"][0]["priority"] == "must"
    assert len(snapshot["constraints"]) == 1
    assert len(snapshot["tickets"]) == 1
    assert len(snapshot["linear_payloads"]) == 1


def test_case_snapshot_returns_none_for_unknown_title(temp_db):
    assert db.get_case_snapshot("Nonexistent Case") is None


def test_migration_adds_missing_columns_to_old_schema(monkeypatch):
    """
    Simulates a database created before priority/acceptance_criteria/constraints
    existed, and confirms init_db() upgrades it in place instead of erroring.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setattr(db, "DB_PATH", tmp.name)

    conn = sqlite3.connect(tmp.name)
    conn.executescript("""
        CREATE TABLE prds (
            prd_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, version INTEGER NOT NULL,
            raw_text TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prd_id INTEGER NOT NULL, req_key TEXT NOT NULL,
            text TEXT NOT NULL, text_hash TEXT NOT NULL
        );
        CREATE TABLE tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            requirement_id INTEGER NOT NULL, title TEXT NOT NULL,
            description TEXT NOT NULL, acceptance_criteria TEXT NOT NULL,
            source_text_hash TEXT NOT NULL, status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

    db.init_db()  # should migrate, not raise

    conn = sqlite3.connect(tmp.name)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(requirements)").fetchall()]
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    os.unlink(tmp.name)

    assert "priority" in cols
    assert "acceptance_criteria" in cols
    assert "constraints" in tables


def _find_stale(temp_db_title):
    from agents.drift_detector import find_stale_tickets
    return find_stale_tickets(temp_db_title)
