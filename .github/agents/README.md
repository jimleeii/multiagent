# .github/agents

This directory contains the orchestrator agent definition, Python runtime, and governance assets.

## Structure

```
.github/agents/
├── Orchestrator.Agent.md              ← Primary orchestrator contract
├── orchestrator/                      ← Python runtime package
│   ├── __init__.py
│   ├── runtime.py                     ← Core orchestration runtime
│   ├── providers.py                   ← Backend provider adapters
│   └── cli.py                         ← CLI entry point
├── internal/                          ← Maintainer-focused docs
│   ├── docs/
│   │   ├── deployment.md
│   │   └── integration-examples.md
├── rules/
└── templates/
```

## Quick Start

1. Install dependencies.

```bash
pip install anthropic aiohttp
```

2. Run the workflow via CLI.

```bash
cd .github/agents
python -m orchestrator.cli \
  --provider mock \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design a resilient cache" \
  --workspace-root ../.. \
  --output json
```

## Iron Rule: Wiki Logs Must Be Updated

The CLI now enforces a mandatory wiki log contract after each orchestration cycle.

- Required files under `.wiki/orchestrator/` are always appended:
  - `Behavior-Log.md`
  - `Behavior-Patterns.md`
  - `Learning-Backlog.md`
  - `Project-Context-Log.md`
  - `Runbook.md`
  - `Skill-Usage-Log.md`
- Default behavior is strict: if any required file is missing or not updated, the run fails.

Flags:

- `--workspace-root <path>`: points to the repository root containing `.wiki/orchestrator`.
- `--wiki-strict` (default): fail run on any log-contract violation.
- `--no-wiki-strict`: report violations without failing the run.

3. Use the documentation map.

- Orchestrator agent definition: [Orchestrator.Agent.md](Orchestrator.Agent.md)
- Deployment and operating model: [internal/docs/deployment.md](internal/docs/deployment.md)
- End-to-end usage examples: [internal/docs/integration-examples.md](internal/docs/integration-examples.md)

## What Lives Where

- Use `Orchestrator.Agent.md` to manage orchestration policy, routing rules, and output contracts.
- Use `orchestrator/` for executable behavior and provider integrations.
- Use `internal/docs/deployment.md` for deployment topology, configuration, and run-time operations.
- Use `internal/docs/integration-examples.md` for concrete invocation samples (CLI, Python, HTTP, and tool handlers).
