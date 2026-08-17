"""
Formatter Agent: no LLM call needed here — this is deterministic mapping,
not generation. Keeping it rule-based avoids hallucinated field names and
keeps the pipeline fast/cheap. Swap in real API calls once you're ready
to create live tickets.
"""


def to_linear_schema(ticket: dict, team_id: str = None) -> dict:
    """Maps our internal ticket dict to Linear's issue-create payload shape."""
    ac_markdown = "\n".join(f"- [ ] {c}" for c in ticket["acceptance_criteria"])
    return {
        "teamId": team_id,
        "title": ticket["title"],
        "description": f"{ticket['description']}\n\n**Acceptance Criteria**\n{ac_markdown}",
        "priority": _priority_to_linear(ticket.get("priority", "should")),
    }


def to_jira_schema(ticket: dict, project_key: str = "YOUR_PROJECT") -> dict:
    """Maps our internal ticket dict to Jira's issue-create payload shape."""
    ac_text = "\n".join(f"* {c}" for c in ticket["acceptance_criteria"])
    return {
        "fields": {
            "project": {"key": project_key},
            "summary": ticket["title"],
            "description": f"{ticket['description']}\n\nAcceptance Criteria:\n{ac_text}",
            "issuetype": {"name": "Story"},
        }
    }


def _priority_to_linear(priority: str) -> int:
    # Linear uses 0 (no priority) to 4 (urgent)
    mapping = {"must": 2, "should": 3, "could": 4}
    return mapping.get(priority, 3)
