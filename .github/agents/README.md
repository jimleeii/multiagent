# .github/agents

This directory hosts the Python runtime package used by the orchestrator workflow and supporting assets.

## Structure

```
.github/agents/
├── Orchestrator.Agent.md              ← Main orchestrator agent definition
├── orchestrator/                        ← Python runtime package
│   ├── __init__.py
│   ├── runtime.py                       ← Core OrchestratorRuntime
│   ├── providers.py                     ← Provider adapters
│   └── cli.py                           ← Command-line entry point
├── internal/                            ← Supporting internal docs
│   ├── docs/
│   │   ├── deployment.md
│   │   └── integration-examples.md
│   └── README.md
├── rules/
└── templates/
```

## Quick Start

1. Install dependencies.

```bash
pip install anthropic aiohttp
```

2. Run the orchestrator CLI.

```bash
cd .github/agents
python -m orchestrator.cli \
  --provider mock \
  --workflow architect-developer-reviewer \
  --architect-prompt "Design a resilient cache" \
  --output json
```

3. Read implementation details.

- Orchestrator agent definition: [Orchestrator.Agent.md](Orchestrator.Agent.md)
- Internal deployment guide: [internal/docs/deployment.md](internal/docs/deployment.md)
- Internal integration examples: [internal/docs/integration-examples.md](internal/docs/integration-examples.md)
- Internal structure notes: [internal/README.md](internal/README.md)
