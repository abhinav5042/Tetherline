"""
Real Linear API integration. Reads credentials from environment variables
ONLY — never accepts a key as a function argument that could accidentally
get logged or hardcoded, and never as a value passed through the UI, in
line with keeping secrets out of chat, code, and version control.

Setup (run once, in your own terminal, never shared):
    Windows (PowerShell):  setx LINEAR_API_KEY "lin_api_..."
    macOS/Linux:           export LINEAR_API_KEY="lin_api_..."

Get your team ID by running get_teams() once and noting the id you want,
then setting it as LINEAR_TEAM_ID the same way.
"""

import os
import requests

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearConfigError(Exception):
    """Raised when required Linear environment variables aren't set."""
    pass


def _headers() -> dict:
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        raise LinearConfigError(
            "LINEAR_API_KEY is not set. Set it as an environment variable "
            "(see module docstring) — never paste it into code or chat."
        )
    return {"Authorization": api_key, "Content-Type": "application/json"}


def get_teams() -> list[dict]:
    """Returns [{"id": ..., "name": ...}, ...] — run this once to find your team ID."""
    query = "{ teams { nodes { id name } } }"
    resp = requests.post(LINEAR_API_URL, headers=_headers(), json={"query": query}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Linear API error: {data['errors']}")
    return data["data"]["teams"]["nodes"]


def create_issue(payload: dict) -> dict:
    """
    Creates a real Linear issue from a payload shaped like
    agents.formatter_agent.to_linear_schema()'s output.
    Returns {"id": ..., "url": ..., "identifier": ...} on success.
    """
    team_id = payload.get("teamId") or os.environ.get("LINEAR_TEAM_ID")
    if not team_id or team_id == "YOUR_TEAM_ID":
        raise LinearConfigError(
            "No Linear team ID configured. Set LINEAR_TEAM_ID as an environment "
            "variable, or run get_teams() to find it."
        )

    mutation = """
    mutation IssueCreate($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { id identifier url }
      }
    }
    """
    variables = {
        "input": {
            "teamId": team_id,
            "title": payload["title"],
            "description": payload.get("description", ""),
            "priority": payload.get("priority", 3),
        }
    }
    resp = requests.post(
        LINEAR_API_URL, headers=_headers(),
        json={"query": mutation, "variables": variables}, timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"Linear API error: {data['errors']}")
    result = data["data"]["issueCreate"]
    if not result["success"]:
        raise RuntimeError("Linear reported issueCreate did not succeed.")
    return result["issue"]


def create_issues_bulk(payloads: list[dict]) -> list[dict]:
    """
    Creates multiple issues, continuing past individual failures rather than
    aborting the whole batch. Returns one result dict per input payload:
    {"title": ..., "success": bool, "url": str|None, "error": str|None}
    """
    results = []
    for payload in payloads:
        try:
            issue = create_issue(payload)
            results.append({
                "title": payload["title"], "success": True,
                "url": issue.get("url"), "error": None,
            })
        except Exception as e:
            results.append({
                "title": payload["title"], "success": False,
                "url": None, "error": str(e),
            })
    return results
