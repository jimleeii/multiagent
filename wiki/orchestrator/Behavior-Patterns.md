# Behavior Patterns

Recurring behavior signatures and what they indicate.

## Pattern Template

### PAT-YYYYMMDD-XXX

- Signal:
- Frequency:
- Impact:
- Affected Subagent(s):
- Likely Cause:
- Proposed Policy Change:
- Status: candidate | applied | rolled_back
- Compaction Batch: CB-YYYYMMDD-XX
- Evidence: [[Behavior-Log#OBS-YYYYMMDD-XXX]]

---

### PAT-20260425-001

- Signal: Intake prompts are sometimes insufficiently normalized before orchestration routing.
- Frequency: 1 observed policy trigger (baseline).
- Impact: Medium; can cause ambiguous subtasks and avoidable clarification cycles.
- Affected Subagent(s): Orchestrator (intake), downstream all subagents.
- Likely Cause: Missing explicit mandatory intake gate requiring normalized prompt construction.
- Proposed Policy Change: Require prompt-optimizer-guided normalization before any direct response or subagent dispatch.
- Status: applied
- Compaction Batch: CB-20260425-01
- Evidence: [[Behavior-Log#OBS-20260425-001]]
