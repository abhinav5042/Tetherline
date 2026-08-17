# PRD Stress Test — Robustness Analysis

Everything tested so far has used one PRD (the fitness-app example), which is a
clean, well-structured PRD with explicit section headers. Real PRDs vary a lot
more than that. Below are three structurally different PRD styles, worked
through by hand (simulating what the parser prompt would actually produce),
to find likely failure modes before spending API credits discovering them
live. Each includes a suggested fix.

---

## Style 1: The terse one-pager (no section headers, just prose)

**Example input:**
> We need a way for support agents to see a customer's order history when
> they open a ticket. Should pull from the orders DB, needs to be fast since
> agents are on the clock with customers waiting. Would be nice to also show
> refund history but not required for v1.

**Likely failure mode:** there's no "Problem Statement" or "Success Metrics"
section for the parser to anchor priority inference on (the fix we made
specifically leans on those sections existing). Priority inference would fall
back to weaker signals — "should pull" and "would be nice" are actually usable
here ("would be nice... not required for v1" is an unusually clear could-signal),
but a terser PRD without such phrasing would leave the model guessing.

**Suggested fix:** add a fallback instruction to the parser prompt: *"If no
Problem Statement or Success Metrics section exists, infer priority from
explicit scoping language in context (e.g. 'not required for v1', 'nice to
have', 'critical path') and default to 'should' when no signal exists at all."*
A default-to-should (rather than default-to-must) avoids re-introducing the
original bug where everything clusters at the top priority.

---

## Style 2: The requirements table (rows, not prose)

**Example input (as markdown table):**
| ID | Requirement | Priority | Notes |
|----|---|---|---|
| R1 | Export report as CSV | P1 | |
| R2 | Export report as PDF | P2 | |
| R3 | Schedule recurring exports | P3 | Post-launch |

**Likely failure mode:** two issues. First, the PRD already HAS an explicit
priority scheme (P1/P2/P3) that doesn't map directly to must/should/could —
the parser might either ignore the existing column (wasteful, and inconsistent
with the PRD's own authority) or map it incorrectly (is P1 "must" or is P3
"must" — some teams number ascending-severity, some descending). Second, the
existing `ID` column (R1, R2, R3) is a natural `req_key` candidate that the
parser might not recognize as one, generating a fresh kebab-case key instead
and losing an existing traceability handle the team already uses.

**Suggested fix:** add to the parser prompt: *"If the PRD already assigns
explicit IDs (e.g. R1, REQ-042, US-12) or an explicit priority scheme (P0/P1,
critical/high/medium), use those directly rather than generating new ones —
preserve the PRD author's own scheme for req_key and priority mapping instead
of inventing a parallel one."* This also has a UX benefit: PMs recognize their
own IDs in the output.

---

## Style 3: The sprawling enterprise PRD (30+ pages, deeply nested)

**Example structure:** multiple product areas each with their own sub-PRDs
embedded in one document, cross-references ("see section 4.2"), and
requirements that depend on each other ("only if R12 is implemented").

**Likely failure mode:** two real risks. First, token budget — GPT-4o has a
large context window but a 30-page PRD plus the system prompt's instructions
risks the model truncating its attention toward the end of the document,
under-extracting later sections. Second, cross-references ("see section 4.2")
won't resolve to anything meaningful once the parser extracts an isolated
requirement — the self-containment instruction we already have ("don't say
'as mentioned above'") helps, but doesn't handle forward/backward references
by section number.

**Suggested fix:** for length — chunk the PRD by its own section headers
before parsing (a fast, cheap pre-processing step, not an LLM call) and run
the parser per-section rather than on the whole document at once, then merge
results. For cross-references — add an instruction: *"If a requirement
references another section number, describe the dependency in plain English
in the requirement text itself (e.g. 'depends on the export feature being
implemented') rather than citing a section number that won't exist in the
extracted output."*

---

## Recommended next step

Rather than guess further, the highest-value use of API credits now is running
these three PRD styles through the actual pipeline once dependencies are set
up, and comparing real output against the predictions above. Where the
predictions are wrong, that's more informative than where they're right — it
means the model handles something more gracefully than expected, or fails in
a way not anticipated here.
