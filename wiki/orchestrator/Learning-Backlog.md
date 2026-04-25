# Learning Backlog

Actionable improvements derived from behavior patterns.

## Item Template

### LRN-YYYYMMDD-XXX

- Priority: low | medium | high | critical
- Problem:
- Proposed Change:
- Scope: routing | skills | contract | acceptance-gate | output-format
- Safety Check:
- Owner: Orchestrator
- Status: pending | in_progress | done | rolled_back
- Linked Pattern: [[Behavior-Patterns#PAT-YYYYMMDD-XXX]]

---

### LRN-20260425-001

- Priority: high
- Problem: Inconsistent prompt normalization at intake can reduce routing precision.
- Proposed Change: Enforce and audit use of a normalized task prompt generated from prompt-optimizer guidance at intake.
- Scope: routing
- Safety Check: Clarify up to 3 questions when critical context is missing; otherwise proceed with explicit assumptions.
- Owner: Orchestrator
- Status: in_progress
- Linked Pattern: [[Behavior-Patterns#PAT-20260425-001]]
