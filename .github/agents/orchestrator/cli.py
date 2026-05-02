#!/usr/bin/env python3
"""CLI entry point for orchestrator workflows.

Usage:
  python cli.py --provider mock --workflow architect-developer-reviewer \\
    --architect-prompt "Design X" \\
    --output json

  python cli.py --provider claude --api-key $ANTHROPIC_API_KEY --workflow ...

  python cli.py --provider copilot --copilot-url http://localhost:3000 --workflow ...
"""

import asyncio
import json
import logging
import sys
from argparse import ArgumentParser
from typing import Optional

from .runtime import DispatchConfig, OrchestratorRuntime, WorkflowResult
from .providers import ClaudeProvider, CopilotProvider, HttpProvider, MockProvider

logger = logging.getLogger("orchestrator.cli")


def setup_logging(verbose: bool = False):
    """Setup logging."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=[handler])


async def run_architect_developer_reviewer(
    runtime: OrchestratorRuntime,
    architect_prompt: str,
    model_map: Optional[dict] = None,
) -> WorkflowResult:
    """Run the canonical 3-stage workflow."""

    def builder_developer(arch_result):
        if arch_result.ok:
            return f"Implement based on: {arch_result.output}"
        return "Implement a minimal fallback solution."

    def builder_reviewer(arch_result, dev_result):
        return f"Review implementation. Architecture ok={arch_result.ok}. Developer ok={dev_result.ok}. Output: {dev_result.output}"

    return await runtime.run_architect_developer_reviewer(
        architect_prompt=architect_prompt,
        developer_prompt_builder=builder_developer,
        reviewer_prompt_builder=builder_reviewer,
        model_map=model_map,
    )


def serialize_workflow_result(result: WorkflowResult) -> dict:
    """Serialize WorkflowResult for JSON/text output."""
    return {
        "ok": result.ok,
        "completed_stages": result.completed_stages,
        "failed_stages": result.failed_stages,
        "results": {
            k: {
                "ok": v.ok,
                "output": v.output,
                "attempts": v.attempts,
                "duration_seconds": v.duration_seconds,
                "error": v.error,
                "timed_out": v.timed_out,
            }
            for k, v in result.results.items()
        },
        "error": result.error,
    }


def main():
    """CLI entry point."""
    parser = ArgumentParser(description="Orchestrator CLI")
    parser.add_argument(
        "--provider",
        choices=["mock", "claude", "copilot", "http"],
        default="mock",
        help="Provider backend",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument(
        "--workflow",
        choices=["architect-developer-reviewer"],
        default="architect-developer-reviewer",
        help="Workflow to run",
    )
    parser.add_argument("--architect-prompt", required=True, help="Initial architect prompt")
    parser.add_argument("--output", choices=["json", "text"], default="text", help="Output format")
    parser.add_argument("--timeout-seconds", type=float, default=45.0, help="Dispatch timeout")
    parser.add_argument("--max-concurrency", type=int, default=4, help="Max concurrent dispatches")
    parser.add_argument("--workspace-root", default=".", help="Workspace root containing .wiki/orchestrator")
    parser.add_argument(
        "--wiki-strict",
        dest="wiki_strict",
        action="store_true",
        default=True,
        help="Fail run when required .wiki/orchestrator logs are not fully updated (default).",
    )
    parser.add_argument(
        "--no-wiki-strict",
        dest="wiki_strict",
        action="store_false",
        help="Do not fail run on wiki log contract violation.",
    )

    # Provider-specific args
    parser.add_argument("--api-key", help="API key (Claude/Copilot)")
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--copilot-url", default="http://localhost:3000", help="Copilot endpoint")
    parser.add_argument("--http-endpoint", help="HTTP provider endpoint")

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Build provider
    if args.provider == "mock":
        provider = MockProvider()
    elif args.provider == "claude":
        provider = ClaudeProvider(api_key=args.api_key, model=args.model or "claude-3-sonnet-20240229")
    elif args.provider == "copilot":
        provider = CopilotProvider(base_url=args.copilot_url)
    elif args.provider == "http":
        if not args.http_endpoint:
            print("Error: --http-endpoint required for http provider", file=sys.stderr)
            sys.exit(1)
        provider = HttpProvider(endpoint=args.http_endpoint)
    else:
        print(f"Unknown provider: {args.provider}", file=sys.stderr)
        sys.exit(1)

    # Build config
    config = DispatchConfig(
        timeout_seconds=args.timeout_seconds,
        max_concurrency=args.max_concurrency,
    )

    # Create runtime
    runtime = OrchestratorRuntime(provider=provider, config=config)

    try:
        # Run workflow
        if args.workflow == "architect-developer-reviewer":
            workflow_result = asyncio.run(
                run_architect_developer_reviewer(runtime, architect_prompt=args.architect_prompt)
            )
        else:
            print(f"Unknown workflow: {args.workflow}", file=sys.stderr)
            sys.exit(1)

        wiki_report = runtime.enforce_wiki_log_contract(
            workspace_root=args.workspace_root,
            architect_prompt=args.architect_prompt,
            workflow_result=workflow_result,
            strict=args.wiki_strict,
        )
        result = serialize_workflow_result(workflow_result)
        result["wiki_log_contract"] = {
            "ok": wiki_report.ok,
            "run_id": wiki_report.run_id,
            "workspace_root": wiki_report.workspace_root,
            "wiki_root": wiki_report.wiki_root,
            "required_files": wiki_report.required_files,
            "updated_files": wiki_report.updated_files,
            "missing_files": wiki_report.missing_files,
            "unchanged_files": wiki_report.unchanged_files,
            "write_errors": wiki_report.write_errors,
            "strict": args.wiki_strict,
        }

        # Output result
        if args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"Workflow ok: {result['ok']}")
            print(f"Completed: {result['completed_stages']}")
            print(f"Failed: {result['failed_stages']}")
            for stage, res in result["results"].items():
                print(f"  {stage}: ok={res['ok']} attempts={res['attempts']} error={res['error']}")
            wiki = result["wiki_log_contract"]
            print(f"Wiki log contract: ok={wiki['ok']} run_id={wiki['run_id']}")
            if not wiki["ok"]:
                print(
                    "  missing="
                    f"{wiki['missing_files']} unchanged={wiki['unchanged_files']} errors={wiki['write_errors']}"
                )

        sys.exit(0 if result["ok"] else 1)
    except Exception as e:
        logger.exception("Workflow failed: %s", e)
        if args.output == "json":
            print(json.dumps({"ok": False, "error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
