# Behavior Log

Use this page for chronological observations of subagent behavior.

## Entry Template

### OBS-YYYYMMDD-XXX

- Timestamp (UTC):
- Request Type:
- Subagent:
- Skills Used:
- Contract Score:
- Outcome: pass | revise | block
- Failure Mode (if any):
- Root Cause Hypothesis:
- Follow-up Action:
- Related: [[Behavior-Patterns#PAT-YYYYMMDD-XXX]] [[Learning-Backlog#LRN-YYYYMMDD-XXX]]
- Compaction Batch: CB-YYYYMMDD-XX

---

### OBS-20260425-001

- Timestamp (UTC): 2026-04-25T10:30:00Z
- Request Type: policy-update
- Subagent: Orchestrator
- Skills Used: prompt-optimizer, agent-customization
- Contract Score: n/a
- Outcome: pass
- Failure Mode (if any): none
- Root Cause Hypothesis: User requests were occasionally routed before prompt intent was fully normalized.
- Follow-up Action: Enforce intake normalization before direct response or dispatch and track impact across 10 cycles.
- Related: [[Behavior-Patterns#PAT-20260425-001]] [[Learning-Backlog#LRN-20260425-001]]
- Compaction Batch: CB-20260425-01
