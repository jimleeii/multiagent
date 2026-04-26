# Project Context Log

Short, descriptive project memory across orchestration runs.

## Quick Trigger Commands

- `context kickoff` -> Run daily startup review and log kickoff context.
- `context sync` -> Log a short checkpoint context entry.
- `skills log` -> Log skills used this cycle into Skill-Usage-Log with reuse note.
- `context snapshot` -> Generate and log current status snapshot.
- `context blocker` -> Log blocker-focused entry with unblock condition.
- `context done` -> Log completion-focused entry.
- `context handoff` -> Log handoff summary with next owner/action.
- `context recall <topic>` -> Retrieve recent context related to a topic before routing.

## Entry Template

### CTX-YYYYMMDD-XXX

- Timestamp (UTC):
- Project/Request:
- Stage: kickoff | in_progress | checkpoint | completed | blocked
- Summary:
  - Completed:
  - In Progress:
  - Blockers/Risks:
  - Next Action:
- Related: [[Behavior-Log#OBS-YYYYMMDD-XXX]] [[Learning-Backlog#LRN-YYYYMMDD-XXX]] [[Runbook#CHG-YYYYMMDD-XXX]]

Rules:

- Keep entries short and descriptive.
- Max 7 bullets in Summary.
- One sentence per bullet.
- No secrets or sensitive data.

---
