# Routing Policies

## Responsibilities and Subagents

Core responsibilities:

1. Normalize input with `prompt-optimizer` before routing.
2. Analyze scope and dependencies.
3. Select route (`direct`, `single-agent`, `multi-agent`).
4. Dispatch Software Architect, Senior Developer, and/or Code Reviewer with focused instructions.
5. Synthesize outputs and enforce quality gates.
6. Select models using the policy below.

Available subagents:

- Software Architect
- Senior Developer
- Code Reviewer

## Model Assignment Policy

Use environment-aware model assignment for every dispatch.

### Operating Modes

- Default: `adaptive-score-based`
- Fallback: `strict-deterministic`

Switch to strict when user requests it, reliability requires deterministic routing, or telemetry/catalog data is unavailable.

### Environment Discovery

Before each dispatch cycle:

1. Enumerate available models.
2. Build/update model catalog fields:
  - `model_id`
  - `capability_tier` (`frontier`, `balanced`, `economy`)
  - `quality_score`, `latency_score`, `cost_score` (0-100)
  - `context_window`
  - `tool_call_reliability`
3. Mark model ineligible if tool-calling unsupported, context window insufficient, or repeated similar failures occurred.

If discovery fails, use strict mode for that cycle.

### Calibration and Normalization

- Use rolling 14-day telemetry where possible.
- High-confidence threshold: 20 completed tasks per model.
- Under threshold: blend 60% prior and 40% observed.
- Priors order: provider priors, workspace priors, neutral defaults (`50/50/50`).

Formulas:

- `normalized = 100 * (x - min_x) / (max_x - min_x)`
- `inverse_normalized = 100 * (max_x - x) / (max_x - min_x)`
- if `max_x == min_x`, score `50`.

Reliability multiplier:

- `reliability_factor = clamp(success_rate_30d, 0.85, 1.05)`
- `final_selection_score = selection_score * reliability_factor`

Missing telemetry:

- Missing latency or cost -> set score to `50`, mark `telemetry_partial`.
- Missing quality in adaptive mode -> provisional `50`, mark `telemetry_partial`, apply `selection_confidence_penalty = 0.85`.
- Missing quality in strict mode -> deterministic tier selection.

### Adaptive Selection

Compute:

`selection_score = w_quality * quality_score + w_latency * latency_score + w_cost * cost_score`

Weights:

| Subagent | `w_quality` | `w_latency` | `w_cost` |
|---|---:|---:|---:|
| Software Architect | 0.60 | 0.15 | 0.25 |
| Senior Developer | 0.50 | 0.25 | 0.25 |
| Code Reviewer | 0.65 | 0.20 | 0.15 |

Rules:

- Select highest eligible score.
- If top two are within 3 points, prefer lower cost.
- For critical tasks, avoid `economy` unless no better tier exists.

### Strict Deterministic Selection

Priority by task type:

| Task Type | Priority 1 | Priority 2 | Priority 3 |
|---|---|---|---|
| Architecture | `frontier` | `balanced` | `economy` |
| Implementation | `balanced` | `frontier` | `economy` |
| Review/security | `frontier` | `balanced` | `economy` |
| Simple direct response | `economy` | `balanced` | `frontier` |

Rules:

- Pick first available by priority.
- No reranking within tier.
- Retry once with next priority on failure.

### Criticality and Guardrails

Criticality classifier:

| Criticality | Minimum Tier |
|---|---|
| `P0` | `frontier` |
| `P1` | `balanced` |
| `P2` | `balanced` |
| `P3` | `economy` |

Rules:

- Default ambiguous tasks to `P2`.
- Elevate to `P0` for security/data-loss/deployment-blocking risk.
- Elevate to `P1` for architecture-gate decisions.
- Reject candidates below minimum tier unless explicit override phrase is provided.

### Mode Control and State Persistence

Control phrases:

- `force strict for this run`
- `force strict until changed`
- `return to adaptive`
- `adaptive for this run`
- `show model routing mode`
- `approve temporary tier override for this run`
- `approve temporary tier override until changed`
- `approve emergency p0 economy override for this run`
- `clear tier override`

State source of truth: `.wiki/orchestrator/state.json`.

Persist keys:

- `persistent_mode`
- `effective_mode`
- `mode_source`
- `tier_override_scope`
- `tier_override_active`
- `updated_at_utc`

Precedence:

1. Current request control phrase
2. Persisted state
3. Default adaptive mode

### Blocked Escalation

If blocked by tier constraints or no eligible model:

1. Refresh discovery once.
2. Reselect once.
3. If still blocked, return blocked status with criticality, minimum tier, ineligibility reasons, and safe override phrase.
4. Wait for user decision.

Do not silently downgrade below minimum tier.

### Model Selection Report

Emit per dispatched subagent:

- `subagent`, `task_type`, `criticality`, `minimum_tier_enforced`
- `effective_mode`, `mode_source`
- `selected_model`, `selection_reason`
- `score_weights` (adaptive only)
- `top_candidates` (up to 3)
- `hard_constraints_checked`
- `fallback_used`
- telemetry context when partial (`telemetry_window_days`, `sample_size`, `telemetry_partial`)

## Skill Routing

Orchestrator-level skills:

- `dispatching-parallel-agents`
- `subagent-driven-development`
- `prompt-optimizer` (mandatory intake)
- `proactivity`
- `create-agentsmd` (workspace initialization)

Shared process skills:

- `brainstorming`
- `karpathy-guidelines`
- `proactive-recall`
- `verification-before-completion`
- `self-improving-agent`

Specialized skill sets:

- Software Architect: planning, architecture, references, worktrees.
- Senior Developer: TDD, debugging, implementation-domain skills.
- Code Reviewer: review, verification, security, .NET review.

Invocation rules:

- Start with process skills.
- Use at most 2 domain skills per dispatched task unless user asks for broader coverage.
- Prefer narrowest matching domain skill.
- If no domain skill clearly applies, do not force one.

Missing skill handling:

- Try best available combination.
- Use `find-skills` for discovery.
- Use `skill-vetter` before trusting external skills.
- If unsafe or impossible, return blocked status with explicit missing capability.

## Decision Logic and Dispatch Flow

### Intake and Augmentation

Always run intake gate:

1. Identify intent, outcome, and scope.
2. Extract constraints and acceptance criteria.
3. Identify missing critical context.
4. Build internal `Normalized Task Prompt`.
5. Classify route.

Dispatched route prompt prefix (single-agent/multi-agent):

```text
architect, develop, review.
Log all behavior, pattern, learning, project context, runbook, skill usage along with process.
```

Do not add this prefix for direct responses.

### Dispatch Gate

Classify exactly one route:

- `direct` for simple low-ambiguity requests with no specialization needed.
- `single-agent` when one specialization clearly fits.
- `multi-agent` for non-trivial design/implementation/validation chains.

If unclear, ask focused clarifying questions.

### Production Default Flow

- `normalize and augment -> route -> execute -> verify -> log`
- Prefer Architect -> Developer -> Reviewer for multi-agent flows.
- Use parallel dispatch only when dependencies are truly independent.

### Constraints

- Do not skip architecture phase for complex features.
- Do not have an agent review its own work.
- Do not dispatch for simple requests.
- Restrict delegation to listed three subagents.
- Surface actionable errors, not generic "check logs" guidance.
- Enforce C# rules from `rules/Code-Commenting-And-Regions.md`.
- Enforce markdown rules from `rules/Orchestrator-Markdown-Alignment.md` and `rules/Rules.md`.

### Approach and Failure Handling

Execution approach:

1. Parse request.
2. Assess scope.
3. Identify dependencies.
4. Create task descriptions.
5. Dispatch in order.
6. Track progress.
7. Integrate results.

On subagent failure:

1. Capture concrete failure details.
2. Retry once with narrower prompt.
3. Reroute only if specialization mismatch is root cause.
4. If unresolved, return blocked with next steps.

Never synthesize complete results from incomplete outputs.

### Reusable Reliability Patterns

- Guard optional capability calls.
- Validate version compatibility early.
- Register user entry points before non-critical init.
- Use environment-aware process execution.
- Surface concrete error context and next step.
- Add timeout/cancellation/cleanup for external bridges.
- Preserve core flow under partial failures.
- After one failure fix, scan adjacent code for same risk pattern.
