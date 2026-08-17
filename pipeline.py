"""
Orchestrates the full PRD -> tickets flow and persists the context-retention
links needed for later drift detection.

Constraints (NFRs like security/performance/compatibility) are matched to
features by req_key and passed into decomposition, but never become their
own requirement/ticket rows — this is what prevents orphaned NFR tickets.
"""

import db
from agents.parser_agent import parse_prd
from agents.decomposition_agent import decompose_requirement
from agents.formatter_agent import to_linear_schema


def _constraints_for(req_key: str, constraints: list[dict]) -> list[dict]:
    matches = []
    for c in constraints:
        applies_to = c.get("applies_to", [])
        if "*" in applies_to or req_key in applies_to:
            matches.append(c)
    return matches


def run_pipeline(prd_title: str, prd_text: str) -> dict:
    """
    Returns a dict with:
      - features: parsed feature requirements
      - constraints: parsed NFR constraints (for visibility, not turned into tickets)
      - tickets: list of tickets, each with its source requirement key
      - linear_payloads: formatted for Linear API
    """
    prd_id = db.save_prd(prd_title, prd_text)
    parsed = parse_prd(prd_text)
    features = parsed["features"]
    constraints = parsed["constraints"]

    for c in constraints:
        db.save_constraint(prd_id, c["text"], c.get("applies_to", []))

    all_tickets = []
    linear_payloads = []

    for req in features:
        requirement_id = db.save_requirement(
            prd_id, req["req_key"], req["text"],
            priority=req.get("priority", "should"),
            acceptance_criteria=req.get("acceptance_criteria", []),
        )
        relevant_constraints = _constraints_for(req["req_key"], constraints)
        tickets = decompose_requirement(req, relevant_constraints)

        for t in tickets:
            t["priority"] = req.get("priority", "should")
            ticket_id = db.save_ticket(
                requirement_id,
                t["title"],
                t["description"],
                t["acceptance_criteria"],
            )
            t["ticket_id"] = ticket_id
            t["source_requirement"] = req["req_key"]
            all_tickets.append(t)
            linear_payloads.append(to_linear_schema(t))

    return {
        "prd_id": prd_id,
        "requirements": features,
        "constraints": constraints,
        "tickets": all_tickets,
        "linear_payloads": linear_payloads,
    }
