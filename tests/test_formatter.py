"""
Tests for agents/formatter_agent.py — deterministic mapping, no LLM calls,
so these run instantly and don't need any API key.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agents.formatter_agent import to_linear_schema, to_jira_schema, _priority_to_linear


def test_priority_mapping_covers_all_levels():
    assert _priority_to_linear("must") == 2
    assert _priority_to_linear("should") == 3
    assert _priority_to_linear("could") == 4


def test_priority_mapping_defaults_for_unknown_value():
    assert _priority_to_linear("not-a-real-priority") == 3


def test_linear_schema_includes_all_acceptance_criteria():
    ticket = {
        "title": "Add shipping filter",
        "description": "Build the filter UI.",
        "acceptance_criteria": ["Shows 3 presets", "Persists on reload"],
        "priority": "must",
    }
    payload = to_linear_schema(ticket, team_id="TEAM123")
    assert payload["teamId"] == "TEAM123"
    assert payload["title"] == "Add shipping filter"
    assert "Shows 3 presets" in payload["description"]
    assert "Persists on reload" in payload["description"]
    assert payload["priority"] == 2


def test_jira_schema_has_correct_shape():
    ticket = {
        "title": "Add shipping filter",
        "description": "Build the filter UI.",
        "acceptance_criteria": ["Shows 3 presets"],
    }
    payload = to_jira_schema(ticket, project_key="PROJ")
    assert payload["fields"]["project"]["key"] == "PROJ"
    assert payload["fields"]["summary"] == "Add shipping filter"
    assert payload["fields"]["issuetype"]["name"] == "Story"
