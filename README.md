# Orchestrator — Production-Grade Anti-Stall Runtime

A resilient Python orchestrator that prevents process halting between subagents via timeout, retry, circuit breaker, and partial-result workflow semantics.

## Key features

- **Per-dispatch timeout** (`asyncio.wait_for`) with retry + exponential backoff
- **Circuit breaker** to stop hammering unhealthy providers
- **Bounded concurrency** (semaphore) to prevent resource starvation
- **Stage transition timeout** to catch hangs between pipeline stages
- **Partial-result workflow**: if Architect fails, Developer still runs with fallback prompt; Reviewer always processes results
- **Health and metrics endpoints** (`/health`, `/metrics`) for monitoring

## Run the demo

```powershell
c:/Users/Wei_Li/AppData/Local/Programs/Python/Python313/python.exe run_orchestrator.py
```

Output shows:
- 3-stage pipeline: Architect → Developer → Reviewer
- Per-stage timeouts and retry behavior
- Metrics endpoint summary
- Clean process exit (no hanging)

## Architecture overview

### Core classes

- `OrchestratorRuntime`: main coordinator with `dispatch()` and `run_architect_developer_reviewer()`
- `SubagentProvider`: protocol for implementing provider adapters (Claude, Copilot, mock)
- `CircuitBreaker`: prevents repeated calls to failing providers
- `DispatchConfig`: timeout, retry, concurrency, and workflow settings
- `DispatchResult` / `WorkflowResult`: structured output

### Provider adapters

Create a `SubagentProvider` to integrate any LLM backend:

```python
class MyProvider:
    async def invoke(self, agent_name, prompt, model=None, metadata=None) -> str:
        # Call your provider (Claude API, Copilot runSubagent, etc.)
        # Enforce timeout at this layer too
        return response_text
        
runtime = OrchestratorRuntime(provider=MyProvider())
```

## Production guide

See [ORCHESTRATOR_PRODUCTION_GUIDE.md](ORCHESTRATOR_PRODUCTION_GUIDE.md) for:

- Why stalls happen and how each pattern prevents them
- Environment-specific deployment (local, CI, service)
- Provider adapter examples
- Observability checklist
- Next-level improvements (persistent queue, fallback routing, SLO dashboards)

## Why this design prevents halting

| Issue | Solution |
|-------|----------|
| Provider hangs on one request | Per-dispatch timeout + retry |
| Repeated requests to unhealthy provider | Circuit breaker (stops after 3 failures) |
| Event loop starved by concurrent requests | Semaphore limits concurrency (default 4) |
| Orchestrator waits forever between stages | Stage transition timeout (20s default) |
| One stage failure halts the entire workflow | Partial-result semantics (continue with fallback) |
| No visibility into what's happening | Lightweight HTTP health + metrics endpoints |

## Configuration

```python
config = DispatchConfig(
    timeout_seconds=45.0,           # per-dispatch timeout
    retries=1,                      # attempt count
    backoff_seconds=0.75,           # exponential backoff base
    max_failures=3,                 # circuit breaker threshold
    circuit_reset_seconds=30.0,     # how long circuit stays open
    max_concurrency=4,              # semaphore bound
    workflow_timeout_seconds=300.0, # total workflow budget
    stage_transition_timeout_seconds=20.0, # between stages
)

runtime = OrchestratorRuntime(provider, config=config)
```

## Monitoring

Health endpoint:

```bash
curl http://127.0.0.1:9000/health
# {"status": "ok", "circuit": "CLOSED"}
```

Metrics endpoint:

```bash
curl http://127.0.0.1:9000/metrics
# dispatch_total 3
# dispatch_success 3
# dispatch_timeout 0
# dispatch_blocked 0
# workflow_total 1
# workflow_success 1
# circuit_state CLOSED
```

## Reference design for multi-LLM environments

To use Claude and GitHub Copilot interchangeably:

1. Define provider adapters:
   - `ClaudeProvider` (calls Claude API with timeout)
   - `CopilotProvider` (calls runSubagent with timeout)
   - `MockProvider` (for tests)

2. Use `model_map` parameter to route:

```python
workflow = await runtime.run_architect_developer_reviewer(
    architect_prompt="...",
    developer_prompt_builder=...,
    reviewer_prompt_builder=...,
    model_map={
        "architect": "claude-3-sonnet",
        "developer": "claude-3-opus",
        "reviewer": "claude-3-sonnet",
    }
)
```

3. Each provider's `invoke()` method handles the model-specific logic.

## Best practices

- Always wrap provider calls with timeouts (in adapter and orchestrator)
- Use circuit breaker thresholds matched to your SLA
- Keep stage transition timeout ≤ 25s; avoid >1m
- Monitor timeout and circuit-open rates
- Test fallback paths (make architect fail in tests)
- Log stage results for triage (not full prompts)

## Troubleshooting

**Process still hangs:**
- Check provider timeout at the adapter layer too
- Reduce `stage_transition_timeout_seconds`
- Lower `max_concurrency` if provider rate-limits

**Workflow always fails:**
- Verify provider is responding (check health endpoint)
- Increase `timeout_seconds` if provider is slow but working
- Check circuit breaker state; if OPEN, provider may be unhealthy

**High timeout/retry rates:**
- May indicate provider is overloaded; add queue depth monitoring
- Or increase timeout if SLA allows; measure p99 latency
- Consider adding a fallback provider for that stage

