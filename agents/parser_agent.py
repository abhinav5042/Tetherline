"""
Parser Agent: takes raw PRD text and extracts structured requirements.

Known failure modes this prompt specifically addresses:
1. Non-functional requirements (security, performance, compatibility, etc.)
   were being extracted as standalone "requirements" and turned into vague,
   orphaned tickets like "Implement encryption for user data in transit" with
   no connection to any actual feature. Fix: NFRs are extracted separately as
   `constraints` and never become their own tickets — they get merged into
   the relevant feature tickets' acceptance criteria instead. (Found via
   testing on a real PRD.)
2. Priority was pattern-matching on the word "must" in PRD boilerplate
   ("the app must track steps..."), so ~75% of requirements came back "must"
   regardless of actual business importance. Fix: the model is given the
   Problem Statement and Success Metrics sections explicitly and told to
   infer priority from what actually drives the stated problem/metrics,
   not from requirement-list phrasing. (Found via testing on a real PRD.)
3. PRDs without a Problem Statement/Success Metrics section, PRDs with their
   own existing ID/priority scheme, and PRDs with internal cross-references
   (e.g. "see section 4.2") were never tested and would likely fail in
   predictable ways. See docs/prd_stress_test.md for the analysis; the
   corresponding prompt instructions below are the fixes. (Found via
   analysis, not yet validated against real PRDs of these styles — that's
   the natural next step.)
"""

import json
from openai import OpenAI

client = OpenAI()

SYSTEM_PROMPT = """You are a PRD parsing agent. Given a raw PRD, extract two things:

1. FEATURES: distinct, atomic, user-facing or system capabilities. Each should be
   small enough to map to roughly one engineering ticket. Do NOT include
   non-functional requirements here (security, performance, scalability, usability,
   compatibility, reliability) — those go in constraints instead.

2. CONSTRAINTS: cross-cutting non-functional requirements that apply to one or more
   features rather than standing alone (e.g. "must encrypt data at rest", "must
   support iOS and Android", "must update in real time with minimal latency").
   For each constraint, list which feature req_keys it most plausibly applies to
   (applies_to). If it applies broadly to most/all features, use applies_to: ["*"].

For priority on features, do NOT just mirror whether the PRD text says "must" or
"should" — that wording is often boilerplate and applied inconsistently across PRDs.
Instead, read the Problem Statement and Success Metrics sections (if present) and
infer priority from what actually drives the core problem and what the success
metrics measure. A feature directly tied to the core problem or a named success
metric is "must". A feature that's supportive but not load-bearing is "should".
A feature that's clearly an enhancement/extra is "could".
If there is no Problem Statement or Success Metrics section, infer priority instead
from explicit scoping language in context (e.g. "not required for v1", "nice to
have", "critical path", "blocking"). If there is no signal at all either way,
default to "should" — do not default to "must", since that reproduces the original
bug where nearly everything ends up tagged as top priority.

If the PRD already assigns its own explicit requirement IDs (e.g. "R1", "REQ-042",
"US-12") or its own explicit priority scheme (e.g. "P0/P1/P2", "Critical/High/Medium"),
use those directly — set req_key from the PRD's own ID (converted to kebab-case) and
map the PRD's own priority scheme onto must/should/could, rather than inventing a
parallel scheme. Preserving the author's own scheme keeps this tool's output
recognizable to the person who wrote the PRD.

If a requirement references another part of the document by number (e.g. "see
section 4.2", "depends on requirement R3"), do not cite that reference in the
extracted requirement text, since the reference won't resolve to anything once
extracted in isolation — instead, describe the dependency in plain English
(e.g. "depends on the export feature being implemented").

For each feature, output:
- req_key: short, stable, kebab-case identifier (e.g. "team-challenges")
- text: the requirement in your own words, 1-3 sentences, self-contained
- acceptance_criteria: 2-4 concrete, testable bullet points (functional only —
  constraints get merged in later, don't duplicate them here)
- priority: "must" | "should" | "could", inferred as described above

For each constraint, output:
- text: the constraint in your own words, 1 sentence
- applies_to: list of req_keys (or ["*"] for broad application)

Respond ONLY with valid JSON, no markdown fences, no preamble. Format:
{
  "features": [
    {
      "req_key": "...",
      "text": "...",
      "acceptance_criteria": ["...", "..."],
      "priority": "must"
    }
  ],
  "constraints": [
    {
      "text": "...",
      "applies_to": ["req-key-1", "req-key-2"]
    }
  ]
}
"""


def parse_prd(prd_text: str) -> dict:
    """Returns {"features": [...], "constraints": [...]}"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prd_text},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    parsed = json.loads(raw)
    return {
        "features": parsed.get("features", []),
        "constraints": parsed.get("constraints", []),
    }
