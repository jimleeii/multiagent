"""Compatibility shim for legacy imports.

Canonical orchestrator runtime lives under .github/agents/orchestrator.
This module re-exports those symbols to keep existing imports working.
"""

from pathlib import Path
import sys

_AGENTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "agents"
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from orchestrator import (  # noqa: E402
    CircuitBreaker,
    ClaudeProvider,
    CopilotProvider,
    DispatchConfig,
    DispatchResult,
    HttpProvider,
    Metrics,
    MockProvider,
    OrchestratorRuntime,
    SubagentProvider,
    WikiLogReport,
    WorkflowResult,
    start_monitoring_server,
)

__all__ = [
    "DispatchConfig",
    "DispatchResult",
    "WorkflowResult",
    "WikiLogReport",
    "SubagentProvider",
    "OrchestratorRuntime",
    "MockProvider",
    "ClaudeProvider",
    "CopilotProvider",
    "HttpProvider",
    "CircuitBreaker",
    "Metrics",
    "start_monitoring_server",
]
