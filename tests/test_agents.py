"""
Tests for the parser and decomposition agents. These mock the OpenAI client
entirely — they test OUR code (JSON parsing, defensive fence-stripping, error
handling), not GPT-4o's actual judgment. Testing the AI's actual output
quality requires running real PRDs through it, which is a separate,
qualitative exercise (see docs/prd_stress_test.md).
"""

import os
import sys
import json
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _mock_response(content: str):
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def test_parser_handles_clean_json():
    from agents import parser_agent
    fake_json = json.dumps({
        "features": [{"req_key": "test-feature", "text": "Do a thing.",
                      "acceptance_criteria": ["It works"], "priority": "must"}],
        "constraints": [],
    })
    with patch.object(parser_agent.client.chat.completions, "create",
                       return_value=_mock_response(fake_json)):
        result = parser_agent.parse_prd("some prd text")
    assert len(result["features"]) == 1
    assert result["features"][0]["req_key"] == "test-feature"


def test_parser_strips_markdown_code_fences():
    """GPT-4o sometimes wraps JSON in ```json fences despite instructions not to — confirm we handle it."""
    from agents import parser_agent
    fenced = "```json\n" + json.dumps({"features": [], "constraints": []}) + "\n```"
    with patch.object(parser_agent.client.chat.completions, "create",
                       return_value=_mock_response(fenced)):
        result = parser_agent.parse_prd("some prd text")
    assert result["features"] == []
    assert result["constraints"] == []


def test_parser_handles_missing_keys_gracefully():
    """If the model returns valid JSON but omits a key, we shouldn't crash."""
    from agents import parser_agent
    incomplete = json.dumps({"features": [{"req_key": "x", "text": "y",
                                            "acceptance_criteria": [], "priority": "should"}]})
    with patch.object(parser_agent.client.chat.completions, "create",
                       return_value=_mock_response(incomplete)):
        result = parser_agent.parse_prd("some prd text")
    assert result["constraints"] == []  # falls back to empty list, doesn't KeyError


def test_decomposition_returns_tickets():
    from agents import decomposition_agent
    fake_json = json.dumps({
        "tickets": [{"title": "Build thing", "description": "desc",
                     "acceptance_criteria": ["ac1"]}]
    })
    requirement = {"req_key": "test", "text": "Do a thing.",
                   "acceptance_criteria": ["It works"], "priority": "must"}
    with patch.object(decomposition_agent.client.chat.completions, "create",
                       return_value=_mock_response(fake_json)):
        tickets = decomposition_agent.decompose_requirement(requirement, [])
    assert len(tickets) == 1
    assert tickets[0]["title"] == "Build thing"


def test_decomposition_passes_constraints_in_request():
    """Confirms constraints are actually sent to the model, not silently dropped."""
    from agents import decomposition_agent
    fake_json = json.dumps({"tickets": [{"title": "t", "description": "d", "acceptance_criteria": []}]})
    requirement = {"req_key": "test", "text": "Do a thing.", "acceptance_criteria": [], "priority": "must"}
    constraints = [{"text": "Must be encrypted", "applies_to": ["test"]}]

    with patch.object(decomposition_agent.client.chat.completions, "create",
                       return_value=_mock_response(fake_json)) as mock_create:
        decomposition_agent.decompose_requirement(requirement, constraints)
        sent_payload = json.loads(mock_create.call_args.kwargs["messages"][1]["content"])
        assert "Must be encrypted" in sent_payload["applicable_constraints"]
