#!/usr/bin/env python3
"""Canonical local demo runner for the orchestrator package.

This script is intended for local validation and mirrors the classic
Architect -> Developer -> Reviewer flow while exercising monitoring and
wiki log contract enforcement.
"""

import argparse
import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    _AGENTS_DIR = Path(__file__).resolve().parents[1]
    if str(_AGENTS_DIR) not in sys.path:
        sys.path.insert(0, str(_AGENTS_DIR))
    from orchestrator.providers import MockProvider
    from orchestrator.runtime import DispatchConfig, OrchestratorRuntime
    from orchestrator.runtime import start_monitoring_server
else:
    from .providers import MockProvider
    from .runtime import DispatchConfig, OrchestratorRuntime
    from .runtime import start_monitoring_server


def build_developer_prompt(arch_result):
    if arch_result.ok:
        return f"Implement based on architecture: {arch_result.output}"
    return "Implement a minimal fallback plan because architecture stage failed."


def build_reviewer_prompt(arch_result, dev_result):
    return (
        "Review implementation output with risk focus. "
        f"Architecture status={arch_result.ok}; Development status={dev_result.ok}. "
        f"Developer output: {dev_result.output}"
    )


async def run_demo(workspace_root: str, monitor_port: int = 9000) -> int:
    provider = MockProvider(
        behavior={
            "Software Architect": {"delay": 0.3, "payload": "Bounded queue + retries + timeouts."},
            "Senior Developer": {"delay": 0.8, "payload": "Implemented resilient dispatch."},
            "Code Reviewer": {"delay": 0.4, "payload": "No critical issues; monitor timeout trends."},
        }
    )

    runtime = OrchestratorRuntime(
        provider=provider,
        config=DispatchConfig(
            timeout_seconds=3.0,
            retries=1,
            backoff_seconds=0.4,
            max_failures=2,
            circuit_reset_seconds=8.0,
            max_concurrency=2,
            workflow_timeout_seconds=20.0,
            stage_transition_timeout_seconds=5.0,
        ),
    )

    server = start_monitoring_server(runtime, host="127.0.0.1", port=monitor_port)

    architect_prompt = "Design anti-stall orchestration for multi-agent pipeline."
    workflow = await runtime.run_architect_developer_reviewer(
        architect_prompt=architect_prompt,
        developer_prompt_builder=build_developer_prompt,
        reviewer_prompt_builder=build_reviewer_prompt,
    )

    wiki_report = runtime.enforce_wiki_log_contract(
        workspace_root=workspace_root,
        architect_prompt=architect_prompt,
        workflow_result=workflow,
        strict=True,
    )

    print("Workflow ok:", workflow.ok)
    print("Completed:", workflow.completed_stages)
    print("Failed:", workflow.failed_stages)
    for stage_name, stage_result in workflow.results.items():
        print(f"{stage_name}: ok={stage_result.ok} attempts={stage_result.attempts} error={stage_result.error}")

    try:
        time.sleep(0.2)
        metrics = urllib.request.urlopen(f"http://127.0.0.1:{monitor_port}/metrics", timeout=2).read().decode()
        health = urllib.request.urlopen(f"http://127.0.0.1:{monitor_port}/health", timeout=2).read().decode()
        print("\nMetrics:\n", metrics)
        print("Health:\n", health)
    except Exception as ex:  # noqa: BLE001
        print(f"Metrics fetch timeout/error (expected in constrained env): {ex}")
    finally:
        try:
            server.server_close()
        except Exception:  # noqa: BLE001
            pass

    print(
        json.dumps(
            {
                "wiki_log_contract": {
                    "ok": wiki_report.ok,
                    "run_id": wiki_report.run_id,
                    "updated_files": wiki_report.updated_files,
                    "missing_files": wiki_report.missing_files,
                    "unchanged_files": wiki_report.unchanged_files,
                    "write_errors": wiki_report.write_errors,
                }
            },
            indent=2,
        )
    )
    return 0 if workflow.ok and wiki_report.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run canonical orchestrator demo with monitoring and log checks")
    parser.add_argument(
        "--workspace-root",
        default=str(Path(__file__).resolve().parents[3]),
        help="Repository root containing .wiki/orchestrator (default: auto-detected)",
    )
    parser.add_argument("--monitor-port", type=int, default=9000, help="Port for /health and /metrics")
    args = parser.parse_args()
    return asyncio.run(run_demo(workspace_root=args.workspace_root, monitor_port=args.monitor_port))


if __name__ == "__main__":
    raise SystemExit(main())
