# Orchestrator Runbook

Document applied policy changes and outcomes.

## Change Record Template

### CHG-YYYYMMDD-XXX

- Date:
- Trigger Pattern:
- Change Applied:
- Expected Effect:
- Validation Window:
- Observed Result:
- Decision: keep | revise | rollback
- Related Entries: [[Behavior-Patterns#PAT-YYYYMMDD-XXX]] [[Learning-Backlog#LRN-YYYYMMDD-XXX]]

---

## Validation Tracker

Use this tracker to evaluate CHG-20260425-001 over the declared 10-cycle window.

### CHG-20260429-001

- Date: 2026-04-29
- Trigger Pattern: workspace init scaffold
- Change Applied: Initialized AGENTS.md and wiki/orchestrator scaffold from templates.
- Expected Effect: Deterministic startup context, logging, and policy traceability for orchestrated runs.
- Validation Window: Next 5 orchestration cycles.
- Observed Result: Scaffold created successfully with required files present.
- Decision: keep
- Related Entries: [[Project-Context-Log#CTX-20260429-001]]

### Validation Criteria

- Prompt normalization was explicitly performed before dispatch.
- Clarifying questions were asked when critical context was missing.
- Dispatched tasks were unambiguous and required no avoidable rerouting.
- Follow-up rework due to intent misinterpretation was reduced.
