# PRD-to-Ticket Automation with Context Retention

Multi-agent system that converts PRDs into engineering tickets while preserving
traceability back to the source requirement — so when the PRD changes, you know
exactly which tickets are now stale.

## Architecture

```
PRD (markdown/text)
   │
   ▼
[Parser Agent]  → structured requirements (problem, user stories, acceptance criteria)
   │
   ▼
[Decomposition Agent] → candidate tickets, each tagged with source requirement ID
   │
   ▼
[Context Store] (SQLite) → persists PRD versions + requirement↔ticket links
   │
   ▼
[Formatter Agent] → Jira/Linear-shaped JSON output
   │
   ▼
[Drift Detector] → on PRD re-upload, diffs against stored version and flags
                    which tickets are affected by which changed requirements
```

## Setup

```bash
pip install -r requirements.txt --break-system-packages
export OPENAI_API_KEY=sk-...
python init_db.py
streamlit run app.py
```

## Running the test suite

```bash
pytest tests/ -v
```

Tests cover the database/drift-detection layer, the deterministic Linear/Jira
formatter, and the parser/decomposition agents (with the OpenAI client mocked
— no API key or network access needed to run these).

## Linear integration (optional)

To create real tickets instead of just previewing the payload, set:

```bash
export LINEAR_API_KEY=lin_api_...
export LINEAR_TEAM_ID=...   # find via agents.linear_client.get_teams()
```

Never paste API keys into chat or commit them to version control — set them
as environment variables only.

## Files

- `db.py` — SQLite schema + context-retention layer (the differentiator),
  with an automatic migration path for schema changes
- `agents/parser_agent.py` — PRD → structured requirements + constraints
- `agents/decomposition_agent.py` — requirements → tickets
- `agents/formatter_agent.py` — tickets → Jira/Linear schema (deterministic)
- `agents/drift_detector.py` — PRD diff → affected-ticket flags
- `agents/linear_client.py` — real Linear API integration
- `app.py` — Streamlit UI
- `pipeline.py` — orchestrates the full run
- `tests/` — automated test suite
- `docs/case_study.md` — portfolio write-up of the project
- `docs/prd_stress_test.md` — analysis of untested PRD styles and their
  likely failure modes

## Demo flow for interviews

1. Paste PRD v1 → generates tickets, each showing "sourced from: Requirement 3 (checkout filter)"
2. Edit PRD v1 → PRD v2, changing Requirement 3's acceptance criteria
3. Re-run → tool flags: "Ticket #4 may need review — its source requirement changed"

This last step is the whole pitch. Everything else is commodity PRD→ticket conversion.
