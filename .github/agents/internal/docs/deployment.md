# Orchestrator Deployment Guide

This document covers production deployment, runtime configuration, and operational checks.
For runnable snippets and end-to-end invocations, see [integration-examples.md](integration-examples.md).

## Purpose

- Define where each orchestrator artifact belongs.
- Explain how the Orchestrator agent invokes Python runtime behavior.
- Provide production defaults and troubleshooting guidance.

## Workspace Layout

```text
.github/agents/
├── Orchestrator.Agent.md
├── orchestrator/
│   ├── __init__.py
│   ├── runtime.py
│   ├── providers.py
│   └── cli.py
├── internal/docs/
│   ├── deployment.md
│   └── integration-examples.md
├── rules/
└── templates/
```

## Invocation Model

`Orchestrator.Agent.md` is an orchestration policy file. It does not execute Python directly.
Execution happens through tools that call the runtime package, typically with:

```bash
python -m orchestrator.cli --provider <provider> --workflow architect-developer-reviewer --architect-prompt "<request>" --output json
```

Supported invocation patterns:

- CLI call from agent tooling (`execute/runInTerminal`).
- Direct Python import of `OrchestratorRuntime`.
- HTTP wrapper service around `OrchestratorRuntime`.

Detailed examples for all three patterns are in [integration-examples.md](integration-examples.md).

## Provider Backends

The runtime supports four provider adapters:

- `MockProvider`: local development and tests.
- `ClaudeProvider`: Anthropic-backed orchestration.
- `CopilotProvider`: Copilot bridge endpoint.
- `HttpProvider`: custom backend endpoint.

## Production Configuration

Default runtime behavior is defined by `DispatchConfig`:

```python
DispatchConfig(
    timeout_seconds=45.0,
    retries=1,
    backoff_seconds=0.75,
    max_failures=3,
    circuit_reset_seconds=30.0,
    max_concurrency=4,
    workflow_timeout_seconds=300.0,
    stage_transition_timeout_seconds=20.0,
)
```

Tuning guidance:

- Increase `timeout_seconds` for slow providers.
- Increase `max_concurrency` only if provider rate limits allow it.
- Increase `circuit_reset_seconds` when backend recovery is slow.

## Environment Setup

```bash
pip install anthropic aiohttp
export ANTHROPIC_API_KEY=sk-ant-...
export COPILOT_SERVICE_URL=http://localhost:3000
```

## Deployment Profiles

### Local Development

- Provider: `mock`
- Storage: in-memory runtime state
- Monitoring: optional `/health` and `/metrics`

### CI/CD

- Provider: `claude` or `copilot`
- Output: JSON artifact for pipeline decisions
- Monitoring: log-based verification

### Production Service

- Provider: `claude` or `http`
- Recommended: persist workflow outcomes and expose health/metrics
- Recommended: alert on timeout and circuit-breaker rates

## Troubleshooting

### Missing dependencies

Symptom: import errors for `anthropic` or `aiohttp`.

```bash
pip install anthropic aiohttp
```

### Provider connection errors

- Confirm endpoint URL and credentials.
- Validate network/firewall route.
- Test provider health endpoint independently.

### Frequent workflow timeouts

- Raise `timeout_seconds` and `workflow_timeout_seconds`.
- Check provider latency and queue depth.
- Reduce `max_concurrency` if backend is saturated.

### Circuit breaker frequently open

- Inspect backend error rates.
- Increase `circuit_reset_seconds` if recovery needs longer.
- Restart runtime only after backend health is restored.

## Operational Checklist

- Verify dependencies are installed.
- Verify environment variables are set for selected provider.
- Run a mock workflow smoke test before using external providers.
- Confirm JSON output is parsed by the caller before rollout.
- Confirm `/health` and `/metrics` are reachable when monitoring is enabled.

## Related Files

- Agent contract: [../../Orchestrator.Agent.md](../../Orchestrator.Agent.md)
- Integration examples: [integration-examples.md](integration-examples.md)

