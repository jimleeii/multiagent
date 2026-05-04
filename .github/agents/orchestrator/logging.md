# Logging Policies

## Behavior Monitoring and Wiki Logging

Track subagent behavior for every orchestration cycle and persist observations in `.wiki/orchestrator/` markdown files.

Coverage rules:

- Every cycle logs behavior, patterns/learning updates, project context, runbook checkpoint, and skill usage.
- Direct-response cycles are included (compact form allowed).
- Dispatched cycles require detailed evidence-backed entries.

### Logging Profiles

- `full` (default): all required wiki artifacts.
- `light`: only
  - `.wiki/orchestrator/Project-Context-Log.md`
  - `.wiki/orchestrator/Runbook.md`
  - `.wiki/orchestrator/Skill-Usage-Log.md`
- `auto`: use `light` only for direct no-dispatch admin phrases:
  - `show model routing mode`
  - `force strict for this run`
  - `force strict until changed`
  - `return to adaptive`
  - `adaptive for this run`
  - `clear tier override`

Guardrails:

- Never use `light` for dispatched workflows.
- Never use `light` when minimum-tier protections are lowered.
- If ambiguous, default to `full`.

Mandatory lifecycle statement per cycle:

- `Log all behavior, pattern, learning, project context, runbook, skill usage along with process.`

### Wiki Storage Layout

- `.wiki/orchestrator/Home.md`
- `.wiki/orchestrator/Project-Context-Log.md`
- `.wiki/orchestrator/Behavior-Log.md`
- `.wiki/orchestrator/Skill-Usage-Log.md`
- `.wiki/orchestrator/Behavior-Patterns.md`
- `.wiki/orchestrator/Learning-Backlog.md`
- `.wiki/orchestrator/Runbook.md`

### Daily Startup Context Review

Before the first orchestration task each day:

1. Read latest project context entries.
2. Read unresolved learning backlog and latest runbook checkpoint.
3. Read `.wiki/orchestrator/state.json` and confirm active routing state.
4. Produce a 3-7 bullet "Today Context" summary:
  - completed work
  - in-progress items
  - highest-risk open items
  - recommended first action

Use the summary to guide routing.

### Context Behavior Triggers

| Trigger | Alias Keywords | Action |
|---|---|---|
| `context kickoff` | `day start`, `start today`, `daily kickoff` | Run daily startup context review and append kickoff entry. |
| `context sync` | `sync context`, `checkpoint context` | Append short checkpoint entry. |
| `skills log` | `log skills`, `skill usage`, `skills used` | Append skill usage entry for current cycle. |
| `context snapshot` | `project snapshot`, `status snapshot` | Produce concise state summary and log checkpoint. |
| `context blocker` | `log blocker`, `blocked context` | Append blocker, impact, unblock condition. |
| `context done` | `mark done`, `complete context` | Append completion entry and follow-up recommendation. |
| `context handoff` | `handoff`, `handover` | Append handoff summary with next owner/action. |
| `context recall <topic>` | `recall`, `find context` | Review recent relevant context and return findings. |
| `workspace init` | `init workspace`, `scaffold workspace`, `setup workspace` | Run full workspace initialization and log results. |

If multiple triggers appear, run in this order:
`workspace init -> context kickoff -> context recall -> context snapshot/context sync -> context blocker/context done/context handoff`.

### What to Monitor Per Dispatch

- Routing quality
- Output quality and contract completeness
- Reliability (retry/reroute/timeout/blocked)
- Efficiency (unnecessary steps or handoffs)
- Risk handling timing

### Required Logging Entries

Behavior log entry per dispatched subagent result in `.wiki/orchestrator/Behavior-Log.md`:

- Entry ID (`OBS-YYYYMMDD-XXX`)
- UTC timestamp
- Request type and selected subagent
- Skills used
- Contract score and pass/revise/block outcome
- Failure mode (if any)
- Root-cause hypothesis
- Follow-up action
- Links to related wiki entries

Skill usage entry per cycle in `.wiki/orchestrator/Skill-Usage-Log.md`:

- Entry ID (`SKL-YYYYMMDD-XXX`)
- UTC timestamp
- Request type
- Routing path (`direct`, `single-agent`, `multi-agent`)
- Subagent(s)
- Skills used in invocation order
- Invocation reason (one sentence)
- Outcome impact (`positive`, `neutral`, `negative`)
- Reuse note

Project context entry after each dispatched cycle, or direct cycle that changes persistent policy/state:

- Max 7 bullets
- One sentence per bullet
- Focus on decisions, outcomes, blockers, next action

Never log secrets, credentials, tokens, or personal data.

### Self-Improvement Loop

After each cycle:

1. Log observations.
2. Detect recurring patterns (same issue 2+ times).
3. Record pattern and open/update learning backlog item.
4. Apply one small targeted orchestration improvement when safe.
5. Record change and expected effect in runbook.

### Improvement Guardrails

- Keep changes small and reversible.
- Change one policy area per cycle unless urgent reliability issue requires more.
- Roll back regressions and record rollback reason.
- Promote proven improvements into permanent policy files.

### Review Cadence

- Every 10 behavior observations: compact duplicate signals into shared pattern entries.
- Every 15 skill-usage entries: summarize recurring high-value skill combos.
- At least every 7 days: triage learning backlog and set explicit unblock conditions for blocked items.
- After triage: append runbook checkpoint summary.
- Daily: run startup context review before first task.
