# Tetherline — PRD-to-Ticket Automation with Context Retention

*A personal project exploring AI-assisted product management workflows.*

## The problem

When a PM manually breaks a PRD into engineering tickets, two things get lost:

1. **The rationale.** A ticket says "add filter dropdown" but not the user
   problem it solves — so engineers make small decisions during
   implementation that drift from the original intent.
2. **Traceability.** If the PRD changes later, there's no mechanism to know
   which existing tickets were built against the now-outdated version of a
   requirement. Teams catch this by accident, if at all.

Tetherline addresses the second problem directly: every ticket keeps a
persistent link back to the exact requirement it came from, including a
hash of that requirement's text at creation time. When the PRD changes, the
tool can tell you precisely which tickets are now stale.

## Architecture

A small multi-agent pipeline, each stage doing one job:

```
PRD (text, or uploaded .txt/.md/.pdf/.docx)
   │
   ▼
Parser Agent        → structured features + constraints (NFRs kept separate)
   │
   ▼
Decomposition Agent  → tickets, with relevant constraints merged into
   │                    each ticket's acceptance criteria
   ▼
Context Store (SQLite) → persists requirement↔ticket links + a hash of each
   │                       requirement's text
   ▼
Drift Detector        → on re-upload, recomputes hashes and flags any ticket
   │                     whose source requirement changed
   ▼
Linear API             → creates real tickets, or previews the payload
```

**Stack:** GPT-4o (via the OpenAI API), SQLite for the context-retention
layer, Streamlit for the UI, the Linear GraphQL API for ticket creation.

## What I found by testing against a real PRD — and how I fixed it

The most useful part of building this wasn't the initial implementation —
it was running a real fitness-app PRD through the pipeline and finding it
broke in specific, informative ways.

**Priority collapsed to "must" for almost everything.** The parser was
pattern-matching on the word "must" in boilerplate PRD language ("the app
must track steps..."), so 9 of 12 requirements came back tagged as top
priority — including things like "compatibility" sitting at the same level
as core features. Fixed by having the model infer priority from the
Problem Statement and Success Metrics sections instead of surface wording,
with a safe default ("should," not "must") when no PRD structure exists to
anchor on.

**Non-functional requirements became orphaned tickets.** Security,
performance, and compatibility requirements were each spawning their own
standalone ticket — e.g. "Implement encryption for user data in transit,"
disconnected from any actual feature. These sit in a backlog forever
because nobody knows which feature they belong to. Fixed by extracting NFRs
into a separate `constraints` list that gets merged into the *relevant*
feature tickets' acceptance criteria instead of becoming tickets of their
own.

**A real SQL bug in the drift-detection logic itself.** The original query
compared a ticket against the specific requirement row it was created
from — but that row is frozen at creation time and never changes. It needed
to compare against the *latest version* of that same requirement (matched
by a stable `req_key`), not its own frozen snapshot. Caught by writing an
actual test: create a ticket, edit the source requirement, check for drift
— the bug was that it reported no drift when it should have.

**A Markdown rendering bug that ate its own tail.** The UI renders custom
HTML cards using `textwrap.dedent()` to fix indentation. One card embeds a
JSON payload preview, and `json.dumps(..., indent=2)` produces lines like
`{` with zero leading spaces — which made `dedent()`'s "find the common
indentation across every line" logic collapse to zero for the *entire*
card, silently undoing the fix. Solved by dedenting the template with a
placeholder before inserting the JSON, so the JSON's own formatting can
never corrupt the surrounding template's indentation.

**Requirement-level data was generated but never actually saved.** Priority
and acceptance criteria were computed by the AI on every run but never
persisted to the database — so reopening a past case showed nothing useful,
even though the tickets themselves were saved correctly. Fixed by adding
the missing columns, with a migration path so existing databases upgrade in
place rather than needing to be deleted.

## Validating the design against PRD styles I hadn't tested yet

Rather than assume the parser generalizes, I worked through three
structurally different PRD styles by hand — a terse one-pager with no
section headers, a requirements table with the author's own ID/priority
scheme, and a long PRD with internal cross-references — to find likely
failure modes before spending API credits discovering them live. Each
predicted failure became a specific prompt instruction (full analysis in
`docs/prd_stress_test.md`). This is a validation step still in progress:
the predictions are reasoned through, not yet confirmed against real runs
of each style.

## Current state

- Multi-agent pipeline, tested end-to-end against a real PRD
- SQLite context-retention layer with an automated test suite (`pytest`)
  covering drift detection, case-history reconstruction, and schema
  migration
- Streamlit UI with case history, file upload, and a Claude-inspired visual
  design
- Real Linear API integration (issue creation, not just payload preview),
  with its own test coverage using a mocked HTTP layer
- A documented, prioritized list of untested edge cases (PRD style
  variation, requirement deletion vs. modification) rather than an implicit
  assumption that everything works

## What I'd do next

- Run the three predicted PRD styles through the real pipeline and compare
  actual output against the predictions
- Handle the case where a requirement is *removed* entirely in a PRD edit
  (currently only *changed* requirements are flagged — a removed
  requirement's tickets silently disappear from view rather than being
  flagged as orphaned)
- Chunk very long PRDs by section before parsing, rather than sending the
  whole document in one call
