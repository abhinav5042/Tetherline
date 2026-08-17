"""
Drift Detector: the payoff feature. Compares a ticket's stored
source_text_hash against the CURRENT hash of its source requirement.
If they differ, the requirement was edited since the ticket was created
and the ticket needs human review.

Deliberately deterministic (no LLM) — drift detection needs to be exact,
not "probably fine."
"""

import db


def find_stale_tickets(prd_title: str) -> list[dict]:
    rows = db.get_all_tickets_with_source(prd_title)
    stale = []
    for row in rows:
        if row["source_text_hash"] != row["current_hash"]:
            stale.append({
                "ticket_id": row["ticket_id"],
                "ticket_title": row["title"],
                "requirement_key": row["req_key"],
                "current_requirement_text": row["requirement_text"],
                "reason": "Source requirement text changed since this ticket was created.",
            })
    return stale
