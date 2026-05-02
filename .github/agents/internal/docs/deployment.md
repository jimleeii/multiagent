# Orchestrator Deployment and Integration Guide

For end-to-end invocation patterns, see [ORCHESTRATOR_INTEGRATION_EXAMPLES.md](integration-examples.md).

## Structure

```
.github/agents/
├── Orchestrator.Agent.md            ← Main orchestrator definition
├── internal/docs/deployment.md    ← This file
├── orchestrator/                   ← Python package
│   ├── __init__.py
│   ├── runtime.py                  ← Core OrchestratorRuntime
│   ├── providers.py                ← Provider adapters
│   └── cli.py                      ← Command-line entry point
├── rules/
│   ├── Code-Commenting-And-Regions.md
│   ├── Orchestrator-Markdown-Alignment.md
│   └── Rules.md
└── templates/
    ├── Home.md
    ├── Project-Context-Log.md
    └── ... (other templates)
```

## How to invoke Python from the Agent

The Orchestrator.Agent.md is a markdown file defining the orchestration agent for VS Code / GitHub Copilot. It does NOT directly run Python. Instead, it uses tools to invoke Python scripts.

### Option 1: Call CLI via `execute/runInTerminal` tool

From the agent, use the `execute/runInTerminal` tool to run:

```bash
cd <workspace_root>
python -m orchestrator.cli \
  --provider claude \
  --api-key $ANTHROPIC_API_KEY \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design a resilient cache." \
  --output json
```

**In agent code (pseudo):**

```python
result = await runInTerminal({
  "command": "cd $WORKSPACE && python -m orchestrator.cli --provider claude --api-key $KEY --workflow architect-developer-reviewer --architect-prompt 'Design X' --output json"
})
```

### Option 2: Embed Python directly in agent

If your agent runtime supports Python execution:

```python
import asyncio
from orchestrator import OrchestratorRuntime, MockProvider

async def run_workflow():
    provider = MockProvider()
    runtime = OrchestratorRuntime(provider)
    result = await runtime.run_architect_developer_reviewer(
        architect_prompt="Design X",
        developer_prompt_builder=lambda arch: f"Implement: {arch.output}",
        reviewer_prompt_builder=lambda arch, dev: f"Review: {dev.output}",
    )
    return result
```

### Option 3: HTTP bridge

If orchestrator is hosted as a service:

```bash
POST /api/workflow
Body: {
  "architect_prompt": "Design X",
  "provider": "claude",
  "model_map": {"architect": "claude-3-opus", ...}
}
Response: {
  "ok": true,
  "completed_stages": ["architect", "developer", "reviewer"],
  "results": {...}
}
```

## Provider Integration Patterns

### Claude (Anthropic)

**Setup:**

```bash
pip install anthropic aiohttp
export ANTHROPIC_API_KEY=sk-ant-...
```

**Usage via CLI:**

```bash
python -m orchestrator.cli \
  --provider claude \
  --model claude-3-opus-20240229 \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design robust error handling for async tasks."
```

**Usage via code:**

```python
from orchestrator import OrchestratorRuntime, ClaudeProvider

provider = ClaudeProvider(model="claude-3-opus-20240229")
runtime = OrchestratorRuntime(provider=provider)
result = await runtime.run_architect_developer_reviewer(...)
```

### GitHub Copilot

**Setup:**

Your Copilot service must expose an HTTP endpoint that accepts:

```json
POST /invoke
{
  "agent": "Software Architect",
  "prompt": "Design X",
  "model": "gpt-4"
}
```

And returns:

```json
{
  "output": "response text"
}
```

**Usage via CLI:**

```bash
python -m orchestrator.cli \
  --provider copilot \
  --copilot-url http://your-copilot-service:3000 \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design X"
```

**Usage via code:**

```python
from orchestrator import OrchestratorRuntime, CopilotProvider

provider = CopilotProvider(base_url="http://localhost:3000")
runtime = OrchestratorRuntime(provider=provider)
result = await runtime.run_architect_developer_reviewer(...)
```

### Custom HTTP Backend

Any LLM service (self-hosted, third-party) can be integrated:

```bash
python -m orchestrator.cli \
  --provider http \
  --http-endpoint http://your-llm-service/api/complete \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design X"
```

## Integration with Orchestrator.Agent.md

Update [Orchestrator.Agent.md](../../Orchestrator.Agent.md) to add execution guidance:

**Example tool call in agent:**

```markdown
## Execution Methods

### Via CLI (subprocess)

The Orchestrator Python package exposes a CLI for programmatic access:

\`\`\`bash
python -m orchestrator.cli \\
  --provider <claude|copilot|http|mock> \\
  --workflow architect-developer-reviewer \\
  --architect-prompt "<your prompt>" \\
  --output json
\`\`\`

### Via Python (direct import)

If the agent runtime supports Python:

\`\`\`python
from orchestrator import OrchestratorRuntime, ClaudeProvider

provider = ClaudeProvider()
runtime = OrchestratorRuntime(provider=provider)
result = await runtime.run_architect_developer_reviewer(...)
\`\`\`

### Via HTTP (if hosted as service)

POST /api/workflow with architect_prompt and provider config.
```

## Example Agent Integration Flow

1. **User request enters Orchestrator.Agent**
   - Agent parses request and creates architect prompt

2. **Agent calls Python CLI**
   ```bash
   python -m orchestrator.cli \
     --provider claude \
     --architect-prompt "user_request_converted_to_prompt"
   ```

3. **CLI runs the 3-stage workflow**
   - Stage 1: Architect designs solution
   - Stage 2: Developer implements based on architect output
   - Stage 3: Reviewer validates implementation

4. **CLI returns JSON result**
   ```json
   {
     "ok": true,
     "completed_stages": ["architect", "developer", "reviewer"],
     "results": { ... }
   }
   ```

5. **Agent processes result and responds to user**

## Deployment Topology

### Local development

- Provider: `MockProvider`
- Storage: In-memory metrics
- Monitoring: Optional HTTP server on port 9000

```bash
python -m orchestrator.cli --provider mock --workflow architect-developer-reviewer --architect-prompt "Test"
```

### CI/CD environment

- Provider: `ClaudeProvider` or `CopilotProvider`
- Storage: Metrics collected in logs
- Monitoring: Parse logs or export to CI dashboard

```bash
# In CI script
export ANTHROPIC_API_KEY=$SECRETS.ANTHROPIC_API_KEY
python -m orchestrator.cli --provider claude --workflow ... --output json > result.json
```

### Production service

- Provider: `ClaudeProvider` or custom HTTP bridge
- Storage: Persist workflow results to database
- Monitoring: Prometheus metrics endpoint or custom exporter

```python
# In Flask/FastAPI app
@app.post("/api/workflow")
async def run_workflow(req):
    provider = ClaudeProvider()
    runtime = OrchestratorRuntime(provider=provider)
    result = await runtime.run_architect_developer_reviewer(...)
    db.save_workflow(result)  # Persist
    return result
```

## Configuration

### Runtime config defaults

```python
DispatchConfig(
    timeout_seconds=45.0,              # Per-dispatch timeout
    retries=1,                         # Retry attempts
    backoff_seconds=0.75,              # Exponential backoff base
    max_failures=3,                    # Circuit breaker threshold
    circuit_reset_seconds=30.0,        # Circuit open duration
    max_concurrency=4,                 # Semaphore bound
    workflow_timeout_seconds=300.0,    # Total workflow budget
    stage_transition_timeout_seconds=20.0, # Between stages
)
```

### Environment variables

```bash
# Claude
export ANTHROPIC_API_KEY=sk-ant-...

# Copilot service
export COPILOT_SERVICE_URL=http://localhost:3000

# Custom HTTP backend
export ORCHESTRATOR_ENDPOINT=http://your-llm-service/api
```

## Troubleshooting

**ImportError: No module named 'anthropic'**

```bash
pip install anthropic aiohttp
```

**ConnectionRefusedError on Copilot provider**

- Verify Copilot service is running at the URL
- Check firewall and network connectivity
- Run `curl http://copilot-url/health` to test

**Workflow timeout**

- Increase `workflow_timeout_seconds` in DispatchConfig
- Or increase per-stage `timeout_seconds`
- Check provider logs for slowness

**Circuit breaker opens**

- Provider is failing repeatedly; check its health
- Increase `circuit_reset_seconds` if provider is recovering slowly
- Or manually reset by creating a fresh `OrchestratorRuntime` instance

## Next steps

1. Create provider adapters for your specific LLM backend
2. Integrate CLI calls into Orchestrator.Agent.md workflow
3. Add persistent workflow storage (database)
4. Expose monitoring endpoints (Prometheus, DataDog, etc.)
5. Add fallback provider logic for high availability
6. Implement SLO dashboards and alerting on timeout/circuit-breaker rates
