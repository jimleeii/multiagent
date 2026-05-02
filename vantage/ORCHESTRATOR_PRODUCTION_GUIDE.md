# Orchestrator Production Guide

## Goal

Build a resilient orchestrator that does not halt when one subagent stalls, fails, or the provider slows down.

## Current Production Design

The runtime in `orchestrator.py` is structured around three concerns:

- Dispatch resilience: timeout, retries, exponential backoff, circuit breaker.
- Flow resilience: stage transition timeout and partial-result workflow semantics.
- Operability: health and metrics endpoints.

## Why stalls happen

Typical causes:

- Provider call hangs (network, queueing, model overload).
- Orchestrator waits forever between stages due to missing transition guard.
- Repeated retries on unhealthy provider with no circuit breaker.
- Unlimited concurrency causes event-loop starvation or provider throttling.

## Hardening patterns implemented

- Per-dispatch timeout via `asyncio.wait_for`.
- Retry with bounded attempts and backoff.
- Circuit breaker to stop hammering unhealthy paths.
- Bounded concurrency with semaphore.
- Stage transition timeout for Architect -> Developer -> Reviewer flow.
- Partial result return instead of total process halt.
- Lightweight health and metrics endpoints.

## Reference pipeline

Canonical sequence:

1. Software Architect
2. Senior Developer
3. Code Reviewer

Behavior:

- If Architect fails, Developer gets fallback prompt and continues.
- If Developer fails, Reviewer still runs with failure context.
- Workflow returns complete status object with per-stage result.

## Environment adapters (Claude, GitHub Copilot, etc.)

Use adapter classes implementing `SubagentProvider.invoke(...)`.

### Adapter contract

Inputs:

- `agent_name`
- `prompt`
- `model` (optional)
- `metadata` (optional)

Output:

- plain string output from provider

### GitHub Copilot adapter sketch

- Map `agent_name` to `runSubagent` target or route in your orchestration layer.
- Include explicit timeout in the call path and propagate provider errors as exceptions.
- Normalize output to text, keep raw payload in `metadata` if needed.

### Claude adapter sketch

- Use Claude API/client call in `invoke`.
- Pass system/user prompt framing from orchestrator.
- Enforce timeout at HTTP client and orchestrator layers.
- Convert rate-limit/transient faults into retriable exceptions.

### Multi-provider strategy

Recommended production strategy:

- Primary provider per stage.
- Optional fallback provider by stage.
- Keep result schema identical across providers.
- Track metrics by provider and stage.

## Production configuration recommendations

Low-risk defaults:

- `timeout_seconds`: 45
- `retries`: 1
- `backoff_seconds`: 0.75
- `max_failures`: 3
- `circuit_reset_seconds`: 30
- `max_concurrency`: 4
- `stage_transition_timeout_seconds`: 20
- `workflow_timeout_seconds`: 300

Tune by stage:

- Architect usually needs the largest timeout.
- Reviewer often needs less than Architect but more than small direct tasks.

## Deployment topology by environment

### Local developer machine

- Single process with in-memory metrics.
- Use `MockProvider` for deterministic tests.
- Fast feedback with low timeout values.

### CI environment

- Run orchestrator smoke tests with deterministic provider stubs.
- Collect metrics output and ensure timeout paths are exercised.

### Production service

- Host as long-running service behind API gateway.
- Export metrics to monitoring stack (Prometheus-compatible endpoint or bridge).
- Persist workflow traces to durable store.
- Add distributed lock/queue if multiple orchestrator instances share tasks.

## Better ways to handle stall problems

Yes. The current refactor is a strong baseline, and these are next-level improvements:

- Queue-based architecture: use a durable queue so workflow state survives restarts.
- Heartbeat checkpoints: write stage progress every few seconds for recovery.
- Dead-letter queue: route permanently failing workflows for manual triage.
- Per-stage fallback models/providers: automatic degrade path when a provider stalls.
- Admission control: reject or defer new jobs when queue latency crosses threshold.
- End-to-end idempotency key per workflow to safely retry after crashes.

## Observability checklist

Track at minimum:

- Dispatch totals, successes, failures, timeouts, blocked-by-circuit.
- Workflow totals, success, partial/failure, workflow timeout.
- p50/p95/p99 stage latency by provider and model.
- Rate-limit and provider error categories.

## Security and reliability checklist

- Do not log secrets or full prompt payloads containing sensitive data.
- Enforce strict outbound timeouts on provider clients.
- Validate provider responses before stage handoff.
- Keep retries bounded to avoid retry storms.
- Add graceful shutdown that stops accepting new work and drains in-flight tasks.

## Suggested implementation roadmap

1. Keep current runtime as the reference core.
2. Add real provider adapters for Copilot and Claude.
3. Add persistent workflow state and queue.
4. Add fallback provider routing policy.
5. Add SLO dashboards and alerting on timeout spikes.
