# Orchestrator Integration Examples

This guide contains executable invocation examples for CLI, Python, HTTP, and agent tool wiring.
For deployment policy, tuning, and operational checks, see [deployment.md](deployment.md).

## 1. Command-Line Interface (CLI)

The simplest method: invoke via subprocess.

### From bash/PowerShell

```bash
# Basic call with Claude provider
python -m orchestrator.cli \
  --provider claude \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design a resilient cache" \
  --output json

# With all options
python -m orchestrator.cli \
  --provider claude \
  --model claude-3-opus-20240229 \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design a resilient cache" \
  --timeout-seconds 60 \
  --max-concurrency 2 \
  --output json \
  --verbose
```

### From Python subprocess

```python
import subprocess
import json

result = subprocess.run(
    [
        "python", "-m", "orchestrator.cli",
        "--provider", "claude",
        "--workflow", "architect-developer-reviewer",
        "--architect-prompt", "Design a resilient cache",
        "--output", "json",
    ],
    capture_output=True,
    text=True,
)

if result.returncode == 0:
    workflow_result = json.loads(result.stdout)
    print(f"Workflow ok: {workflow_result['ok']}")
else:
    print(f"Error: {result.stderr}")
```

### From the Orchestrator.Agent

Using the `execute/runInTerminal` tool:

```python
# In agent code (pseudo)
result = await runInTerminal(
    command=(
        "cd $WORKSPACE/.github/agents && "
        "python -m orchestrator.cli "
        "--provider claude "
        "--workflow architect-developer-reviewer "
        f'--architect-prompt "{user_prompt}" '
        "--output json"
    )
)
workflow = json.loads(result.output)
# Process workflow result
```

## 2. Direct Python Import

For code that can directly import the orchestrator package.

### Basic usage

```python
import asyncio
from orchestrator import OrchestratorRuntime, ClaudeProvider, DispatchConfig

async def main():
    config = DispatchConfig(
        timeout_seconds=45.0,
        retries=1,
        max_concurrency=4,
    )
    
    provider = ClaudeProvider()
    runtime = OrchestratorRuntime(provider=provider, config=config)
    
    result = await runtime.run_architect_developer_reviewer(
        architect_prompt="Design a resilient cache system",
        developer_prompt_builder=lambda arch: (
            f"Implement based on: {arch.output}" 
            if arch.ok 
            else "Implement a minimal fallback"
        ),
        reviewer_prompt_builder=lambda arch, dev: (
            f"Review: Architecture ok={arch.ok}. "
            f"Implementation ok={dev.ok}. Output: {dev.output}"
        ),
    )
    
    print(f"Workflow ok: {result.ok}")
    for stage in result.completed_stages:
        res = result.results[stage]
        print(f"  {stage}: {res.output[:100]}...")

asyncio.run(main())
```

### With monitoring server

```python
from orchestrator import start_monitoring_server

config = DispatchConfig(timeout_seconds=45.0, max_concurrency=4)
runtime = OrchestratorRuntime(provider=provider, config=config)

# Start monitoring server in background
server = start_monitoring_server(runtime, host="127.0.0.1", port=9000)

# Run workflow
result = await runtime.run_architect_developer_reviewer(...)

# Check metrics
metrics = runtime.metrics.snapshot()
print(f"dispatch_total: {metrics.get('dispatch_total', 0)}")
print(f"dispatch_success: {metrics.get('dispatch_success', 0)}")
print(f"circuit_state: {runtime.circuit.state}")
```

### With custom provider

```python
from orchestrator import OrchestratorRuntime, HttpProvider

provider = HttpProvider(endpoint="http://your-llm-service/api/complete")
runtime = OrchestratorRuntime(provider=provider)
result = await runtime.run_architect_developer_reviewer(...)
```

## 3. HTTP Service

Host orchestrator as a microservice.

### FastAPI example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator import OrchestratorRuntime, ClaudeProvider, DispatchConfig

app = FastAPI()

# Initialize orchestrator
provider = ClaudeProvider()
config = DispatchConfig(timeout_seconds=45.0, max_concurrency=4)
runtime = OrchestratorRuntime(provider=provider, config=config)


class WorkflowRequest(BaseModel):
    architect_prompt: str
    model: str = "claude-3-sonnet-20240229"


@app.post("/api/workflow")
async def run_workflow(req: WorkflowRequest):
    try:
        def builder_dev(arch_result):
            if arch_result.ok:
                return f"Implement: {arch_result.output}"
            return "Implement minimal fallback"
        
        def builder_review(arch_result, dev_result):
            return f"Review implementation. Architecture ok={arch_result.ok}. Dev ok={dev_result.ok}."
        
        result = await runtime.run_architect_developer_reviewer(
            architect_prompt=req.architect_prompt,
            developer_prompt_builder=builder_dev,
            reviewer_prompt_builder=builder_review,
            model_map={
                "architect": req.model,
                "developer": req.model,
                "reviewer": req.model,
            }
        )
        
        return {
            "ok": result.ok,
            "completed_stages": result.completed_stages,
            "failed_stages": result.failed_stages,
            "results": {
                k: {
                    "ok": v.ok,
                    "output": v.output,
                    "attempts": v.attempts,
                    "error": v.error,
                }
                for k, v in result.results.items()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {
        "status": "ok" if runtime.circuit.state != "OPEN" else "degraded",
        "circuit": runtime.circuit.state,
    }


@app.get("/metrics")
async def metrics():
    return runtime.metrics.snapshot()
```

**Run it:**

```bash
pip install fastapi uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000
```

**Call it:**

```bash
curl -X POST http://localhost:8000/api/workflow \
  -H "Content-Type: application/json" \
  -d '{"architect_prompt": "Design a cache", "model": "claude-3-opus-20240229"}'
```

### Flask example

```python
from flask import Flask, request, jsonify
from orchestrator import OrchestratorRuntime, ClaudeProvider

app = Flask(__name__)
provider = ClaudeProvider()
runtime = OrchestratorRuntime(provider=provider)


@app.route("/api/workflow", methods=["POST"])
async def run_workflow():
    data = request.get_json()
    architect_prompt = data.get("architect_prompt")
    
    result = await runtime.run_architect_developer_reviewer(
        architect_prompt=architect_prompt,
        developer_prompt_builder=lambda arch: f"Implement: {arch.output}",
        reviewer_prompt_builder=lambda arch, dev: f"Review: {dev.output}",
    )
    
    return jsonify({
        "ok": result.ok,
        "results": {
            k: {"ok": v.ok, "output": v.output}
            for k, v in result.results.items()
        }
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
```

## 4. Agent Tool Integration

If your agent runtime supports tool invocation, define an orchestrator tool.

### Agent manifest (pseudo)

```yaml
tools:
  - id: orchestrator.run_workflow
    name: Run Orchestrator Workflow
    description: Execute a multi-stage architecture→development→review workflow
    input_schema:
      type: object
      properties:
        architect_prompt:
          type: string
          description: Initial architecture prompt
        provider:
          type: string
          enum: [claude, copilot, mock]
          default: claude
        model:
          type: string
          description: LLM model name
      required: [architect_prompt]
```

### Agent handler

```python
async def handle_orchestrator_tool(tool_input):
    provider_name = tool_input.get("provider", "claude")
    
    if provider_name == "claude":
        provider = ClaudeProvider()
    elif provider_name == "copilot":
        provider = CopilotProvider()
    elif provider_name == "mock":
        provider = MockProvider()
    
    runtime = OrchestratorRuntime(provider=provider)
    
    result = await runtime.run_architect_developer_reviewer(
        architect_prompt=tool_input["architect_prompt"],
        developer_prompt_builder=lambda arch: f"Implement: {arch.output}",
        reviewer_prompt_builder=lambda arch, dev: f"Review: {dev.output}",
        model_map={"architect": tool_input.get("model")} if tool_input.get("model") else None,
    )
    
    return {
        "ok": result.ok,
        "completed_stages": result.completed_stages,
        "failed_stages": result.failed_stages,
        "results": {k: {"ok": v.ok, "output": v.output} for k, v in result.results.items()}
    }
```

## 5. Integration Patterns

### Pattern: Call via subprocess and parse JSON

Best for: agent-to-orchestrator calls without direct Python import

```python
import subprocess
import json

async def orchestrate_workflow(prompt: str) -> dict:
    result = subprocess.run(
        ["python", "-m", "orchestrator.cli",
         "--provider", "claude",
         "--workflow", "architect-developer-reviewer",
         "--architect-prompt", prompt,
         "--output", "json"],
        capture_output=True,
        text=True,
        timeout=300,  # 5 min total timeout
    )
    
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr}
    
    return json.loads(result.stdout)
```

### Pattern: Dispatch with fallback provider

Best for: high availability

```python
import asyncio
from orchestrator import OrchestratorRuntime, ClaudeProvider, CopilotProvider

async def orchestrate_with_fallback(prompt: str) -> dict:
    providers = [
        ("claude", ClaudeProvider()),
        ("copilot", CopilotProvider(base_url="http://localhost:3000")),
    ]
    
    for name, provider in providers:
        try:
            runtime = OrchestratorRuntime(provider=provider)
            result = await asyncio.wait_for(
                runtime.run_architect_developer_reviewer(
                    architect_prompt=prompt,
                    developer_prompt_builder=lambda arch: f"Implement: {arch.output}",
                    reviewer_prompt_builder=lambda arch, dev: f"Review: {dev.output}",
                ),
                timeout=60,
            )
            if result.ok:
                return result
        except (asyncio.TimeoutError, Exception) as e:
            print(f"Provider {name} failed: {e}, trying next...")
    
    return {"ok": False, "error": "All providers exhausted"}
```

### Pattern: Cache workflow results

Best for: avoiding repeated invocations

```python
import hashlib
import json
from datetime import datetime, timedelta

class OrchestratorWithCache:
    def __init__(self, runtime, cache_ttl_minutes=60):
        self.runtime = runtime
        self.cache = {}
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
    
    async def run_with_cache(self, prompt: str) -> dict:
        key = hashlib.sha256(prompt.encode()).hexdigest()
        
        # Check cache
        if key in self.cache:
            result, timestamp = self.cache[key]
            if datetime.now() - timestamp < self.cache_ttl:
                print(f"Cache hit for prompt hash {key[:8]}...")
                return result
        
        # Run workflow
        result = await self.runtime.run_architect_developer_reviewer(...)
        self.cache[key] = (result, datetime.now())
        
        return result
```

## Operational Notes

- Provider selection, environment setup, and timeout tuning are documented in [deployment.md](deployment.md).
- The runtime already supports partial results and retry/circuit-breaker behavior through `DispatchConfig`.
- Prefer these examples when you need implementation wiring; prefer deployment guidance for production operations.

---

**See [../../README.md](../../README.md), [deployment.md](deployment.md), and [Orchestrator.Agent.md](../../Orchestrator.Agent.md) for more details.**
