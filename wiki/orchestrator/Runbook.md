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

## Change Records

### CHG-20260425-001

- Date: 2026-04-25
- Trigger Pattern: Repeated need to improve user prompt accuracy before orchestration.
- Change Applied: Added mandatory intake rule to normalize user input with `prompt-optimizer` guidance before direct response or subagent dispatch.
- Expected Effect: Higher task clarity at dispatch time, fewer ambiguous subtasks, and reduced rework from misinterpreted intent.
- Validation Window: Next 10 orchestration cycles.
- Observed Result: Pending.
- Decision: keep
- Related Entries: [[Behavior-Patterns#PAT-20260425-001]] [[Learning-Backlog#LRN-20260425-001]]

## Validation Tracker

Use this tracker to evaluate CHG-20260425-001 over the declared 10-cycle window.

### Validation Criteria

- Prompt normalization was explicitly performed before dispatch.
- Clarifying questions were asked when critical context was missing.
- Dispatched tasks were unambiguous and required no avoidable rerouting.
- Follow-up rework due to intent misinterpretation was reduced.

### CHG-20260425-001 Cycle Log

| Cycle | Date | Normalized Prompt Confirmed | Clarification Needed | Reroute Needed | Rework From Misinterpretation | Notes |
|---|---|---|---|---|---|---|
| 1 | 2026-04-25 | yes | no | no | no | Policy update cycle based on OBS-20260425-001 baseline. |
| 2 | TBD | TBD | TBD | TBD | TBD |  |
| 3 | TBD | TBD | TBD | TBD | TBD |  |
| 4 | TBD | TBD | TBD | TBD | TBD |  |
| 5 | TBD | TBD | TBD | TBD | TBD |  |
| 6 | TBD | TBD | TBD | TBD | TBD |  |
| 7 | TBD | TBD | TBD | TBD | TBD |  |
| 8 | TBD | TBD | TBD | TBD | TBD |  |
| 9 | TBD | TBD | TBD | TBD | TBD |  |
| 10 | TBD | TBD | TBD | TBD | TBD |  |
