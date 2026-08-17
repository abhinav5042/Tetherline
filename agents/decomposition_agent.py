"""
Decomposition Agent: takes a single structured feature requirement (plus any
constraints that apply to it) and turns it into one or more engineering tickets.

Constraints are merged into the ticket's acceptance criteria rather than
becoming their own tickets — this is what prevents orphaned tickets like
"Implement encryption for user data in transit" that have no connection to
an actual feature.
"""

import json
from openai import OpenAI

client = OpenAI()

SYSTEM_PROMPT = """You are a ticket decomposition agent. Given one PRD feature
requirement and a list of constraints that apply to it, decide whether it should
become one ticket or multiple (split by concern: backend, frontend, infra,
analytics). Prefer one ticket unless the requirement clearly spans multiple systems.

Incorporate the given constraints as ADDITIONAL acceptance criteria on the
appropriate ticket(s) — do not create separate tickets for constraints, and do not
skip them either. If a constraint doesn't clearly apply to any of the tickets you're
creating for this requirement, you can omit it.

For each ticket, output:
- title: short, action-oriented (e.g. "Add server-side filter API for checkout")
- description: 2-4 sentences explaining WHAT to build and WHY (preserve the
  requirement's intent, don't just restate the title)
- acceptance_criteria: list of testable bullet points — combine the requirement's
  own criteria with any relevant constraints, written as normal bullets (don't
  label which ones came from constraints)

Respond ONLY with valid JSON, no markdown fences. Format:
{
  "tickets": [
    {
      "title": "...",
      "description": "...",
      "acceptance_criteria": ["...", "..."]
    }
  ]
}
"""


def decompose_requirement(requirement: dict, constraints: list[dict] = None) -> list[dict]:
    constraints = constraints or []
    payload = {
        "requirement": requirement,
        "applicable_constraints": [c["text"] for c in constraints],
    }
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(raw)
    return parsed["tickets"]
