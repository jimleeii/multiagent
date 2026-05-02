import asyncio
import os
import sys
import threading
import time
import urllib.request

from orchestrator import DispatchConfig
from orchestrator import MockProvider
from orchestrator import OrchestratorRuntime
from orchestrator import start_monitoring_server


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


async def main():
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

    server = start_monitoring_server(runtime, host="127.0.0.1", port=9000)

    workflow = await runtime.run_architect_developer_reviewer(
        architect_prompt="Design anti-stall orchestration for multi-agent pipeline.",
        developer_prompt_builder=build_developer_prompt,
        reviewer_prompt_builder=build_reviewer_prompt,
    )

    print("Workflow ok:", workflow.ok)
    print("Completed:", workflow.completed_stages)
    print("Failed:", workflow.failed_stages)
    for stage_name, stage_result in workflow.results.items():
        print(f"{stage_name}: ok={stage_result.ok} attempts={stage_result.attempts} error={stage_result.error}")

    try:
        time.sleep(0.2)
        try:
            metrics = urllib.request.urlopen("http://127.0.0.1:9000/metrics", timeout=2).read().decode()
            health = urllib.request.urlopen("http://127.0.0.1:9000/health", timeout=2).read().decode()
            print("\nMetrics:\n", metrics)
            print("Health:\n", health)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"Metrics fetch timeout/error (expected): {e}")
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        # Close socket without blocking (server runs in daemon thread)
        try:
            server.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # Force exit after 5 seconds to avoid daemon thread hangs
        def _timeout_exit():
            time.sleep(5.0)
            print("(force exit due to daemon threads)")
            os._exit(0)
        
        exit_thread = threading.Thread(target=_timeout_exit, daemon=False)
        exit_thread.start()
        sys.exit(0)
