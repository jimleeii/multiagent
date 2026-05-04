# Quality Gates

## Subagent Output Contracts

### Software Architect Contract

Required artifacts:

- Problem framing (scope, constraints, non-goals)
- At least 2 viable approaches with trade-offs
- Recommended architecture and rationale
- Interface and boundary definitions
- Risk register with mitigations
- Validation strategy

### Senior Developer Contract

Required artifacts:

- Implementation summary tied to approved architecture
- Files/components changed (or change plan in read-only cases)
- Test evidence (what ran, pass/fail, gaps)
- Error handling and rollback/guardrail notes
- Known limitations and follow-up actions
- C# commenting/region compliance statement for changed `.cs` files

### Code Reviewer Contract

Required artifacts:

- Findings ordered by severity (Critical, High, Medium, Low)
- Concrete evidence per finding (location, behavior, impact)
- Regression/security/performance risk assessment
- Ship recommendation (`ship`, `ship-with-followups`, `do-not-ship`)
- Required fixes vs optional improvements
- C# commenting/region audit result with violations and severity when present

## Acceptance Gate Before Synthesis

Before final orchestrator synthesis:

- Verify each dispatched subagent contract is complete.
- If required artifacts are missing, request one revision pass.
- If still incomplete, mark status blocked with explicit gaps.
- Never present aggregate output as complete while any contract fails.

Revision cycle cap per subagent and cycle:

- Automatic revision: 1
- Optional second pass: only with explicit user approval in current cycle
- Otherwise: blocked

## Output Quality Scoring Rubric

Artifact scoring:

- `0`: missing or unusable
- `1`: present but weak/ambiguous
- `2`: complete, specific, actionable

Per-subagent maximum: 12 points (6 artifacts x 2).

Thresholds:

- Initial pass:
  - `Pass`: no artifact scored 0 and total >= 80%
  - `Revise`: any artifact scored 0, or total < 80%
- After one revision:
  - `Pass`: no artifact scored 0 and total >= 80%
  - `Revise`: total 60-79% with no zero-score artifacts only if user approved second pass
  - `Block`: total 60-79% without second-pass approval
  - `Block`: any artifact scored 0, or total < 60%

Hard-fail auto-revise conditions regardless of total score:

- Missing test evidence for implementation tasks
- Missing severity ordering in review output
- Architecture recommendation without trade-off rationale

## Output Format Requirements

### Direct Route Output (`direct`)

Return:

1. Routing decision (`direct`) with short reason
2. Answer
3. Assumptions and risks (only when non-trivial)
4. Verification status (validated vs not validated)

### Dispatched Route Output (`single-agent` or `multi-agent`)

Return:

1. Model routing decision
2. Analysis summary
3. Delegation strategy
4. Task descriptions sent to subagent(s)
5. Results summary
6. Escalation status
7. Next steps
8. Assumptions and risks
9. Verification status
10. Behavior learning update

Also include:

- Model selection report per dispatch
- Dispatch choice rationale (`direct` vs `single-agent` vs `multi-agent`)
- Architecture gate outcome (if triggered)
- Retries/reroutes under failure protocol
- Escalation result (`none` or `blocked`) and any user-approved override phrase

## Pre-Finalization Compliance Checklist

Before final response, verify:

- Model routing decision exists for each dispatched subagent.
- Model selection report has required fields.
- Criticality and minimum tier were enforced.
- Adaptive mode includes calibrated scoring or telemetry-partial handling.
- Strict mode follows deterministic priority with no hidden reranking.
- Blocked selection includes escalation status and retry attempts.
- Override usage includes explicit user phrase and visible risk note.
- Route-specific output format is fully followed.
- Behavior/context logs include mode changes, overrides, and fallback reasons.

If any check fails, return blocked with corrective action.

## Automation and Tool Use

- Use templates for structured outputs and logs.
- Always execute behavior monitoring and wiki logging for every cycle using profile rules.
- Always run learning-loop updates and small reversible improvements.
- Always keep project context and skill usage logs current.
- Always follow skill invocation, missing-skill handling, and escalation rules.
