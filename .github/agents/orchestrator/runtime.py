"""Core orchestrator runtime with timeout, retry, and circuit breaker."""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger("orchestrator.runtime")


class SubagentProvider(Protocol):
    """Contract for provider implementations (Claude, Copilot, Mock, etc.)."""

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Invoke an agent from a specific environment/provider."""


@dataclass
class DispatchConfig:
    """Tuning parameters for dispatch behavior."""

    timeout_seconds: float = 45.0
    retries: int = 1
    backoff_seconds: float = 0.75
    max_failures: int = 3
    circuit_reset_seconds: float = 30.0
    max_concurrency: int = 4
    workflow_timeout_seconds: float = 300.0
    stage_transition_timeout_seconds: float = 20.0


@dataclass
class DispatchResult:
    """Result of a single dispatch call."""

    agent_name: str
    ok: bool
    output: str = ""
    attempts: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    timed_out: bool = False


@dataclass
class WorkflowResult:
    """Result of a complete Architect→Developer→Reviewer workflow."""

    ok: bool
    completed_stages: List[str] = field(default_factory=list)
    failed_stages: List[str] = field(default_factory=list)
    results: Dict[str, DispatchResult] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class WikiLogReport:
    """Summary of wiki log writes and verification for one orchestration cycle."""

    ok: bool
    workspace_root: str
    wiki_root: str
    required_files: List[str] = field(default_factory=list)
    updated_files: List[str] = field(default_factory=list)
    missing_files: List[str] = field(default_factory=list)
    unchanged_files: List[str] = field(default_factory=list)
    write_errors: Dict[str, str] = field(default_factory=dict)
    run_id: str = ""


class Metrics:
    """Thread-safe metrics collector."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counts: Dict[str, int] = {}

    def inc(self, key: str, value: int = 1) -> None:
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + value

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counts)


class CircuitBreaker:
    """Simple circuit breaker to prevent hammering unhealthy providers."""

    def __init__(self, max_failures: int = 3, reset_timeout: float = 30.0):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = "CLOSED"  # CLOSED, OPEN, HALF
        self._opened_at: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state != "CLOSED":
                logger.info("circuit: closing after success")
            self._state = "CLOSED"
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            logger.info("circuit: failure recorded (%d/%d)", self._failures, self.max_failures)
            if self._failures >= self.max_failures:
                self._state = "OPEN"
                self._opened_at = time.time()
                logger.warning("circuit: opened for %.1fs", self.reset_timeout)

    def allow_request(self) -> bool:
        with self._lock:
            if self._state == "CLOSED":
                return True
            if self._state == "OPEN":
                if self._opened_at is not None and (time.time() - self._opened_at > self.reset_timeout):
                    self._state = "HALF"
                    logger.info("circuit: moving to HALF state")
                    return True
                return False
            if self._state == "HALF":
                return True
            return False


class OrchestratorRuntime:
    """Production-oriented orchestrator runtime.

    Prevents stalls via:
    - Per-dispatch timeout and retry with backoff.
    - Circuit breaker for unhealthy providers.
    - Bounded concurrency via semaphore.
    - Stage transition timeout.
    - Partial-result workflow semantics (no global halt).
    """

    def __init__(self, provider: SubagentProvider, config: Optional[DispatchConfig] = None):
        self.provider = provider
        self.config = config or DispatchConfig()
        self.metrics = Metrics()
        self.circuit = CircuitBreaker(
            max_failures=self.config.max_failures,
            reset_timeout=self.config.circuit_reset_seconds,
        )
        self._semaphore = asyncio.Semaphore(self.config.max_concurrency)
        self._last_progress_ts = time.monotonic()

    PROMPT_PREFIX_LINES = (
        "architect, develop, review.",
        "Log all behavior, pattern, learning, project context, runbook, skill usage along with process.",
    )

    REQUIRED_WIKI_FILES = (
        "Behavior-Log.md",
        "Behavior-Patterns.md",
        "Learning-Backlog.md",
        "Project-Context-Log.md",
        "Runbook.md",
        "Skill-Usage-Log.md",
    )

    LIGHT_WIKI_FILES = (
        "Project-Context-Log.md",
        "Runbook.md",
        "Skill-Usage-Log.md",
    )

    LOW_RISK_DIRECT_ADMIN_PHRASES = {
        "show model routing mode",
        "force strict for this run",
        "force strict until changed",
        "return to adaptive",
        "adaptive for this run",
        "clear tier override",
    }

    ROUTING_STATE_FILE = Path(".wiki") / "orchestrator" / "state.json"
    ALLOWED_PERSISTENT_MODES = {"adaptive-score-based", "strict-deterministic"}
    ALLOWED_TIER_OVERRIDE_SCOPES = {"none", "one-run", "persistent"}
    ROUTING_STATE_TEMPLATE_FILE = Path(".github") / "agents" / "templates" / "state.json"

    def _mark_progress(self) -> None:
        self._last_progress_ts = time.monotonic()

    @staticmethod
    def _augment_prompt(user_request: str) -> str:
        """Apply the mandatory prompt contract once, without duplicate prefix lines."""
        normalized = (user_request or "").strip()
        for line in OrchestratorRuntime.PROMPT_PREFIX_LINES:
            if normalized.lower().startswith(line.lower()):
                normalized = normalized[len(line) :].lstrip()
        prefix = "\n".join(OrchestratorRuntime.PROMPT_PREFIX_LINES)
        return f"{prefix}\n\n{normalized}" if normalized else prefix

    async def _invoke_once(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> str:
        try:
            return await asyncio.wait_for(
                self.provider.invoke(agent_name=agent_name, prompt=prompt, model=model, metadata=metadata),
                timeout=self.config.timeout_seconds,
            )
        except asyncio.TimeoutError as ex:
            raise TimeoutError(f"operation timed out after {self.config.timeout_seconds}s") from ex

    async def dispatch(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DispatchResult:
        """Dispatch a single agent call with timeout, retry, and circuit breaker."""
        self.metrics.inc("dispatch_total")
        start = time.monotonic()
        attempts = 0

        if not self.circuit.allow_request():
            self.metrics.inc("dispatch_blocked")
            return DispatchResult(
                agent_name=agent_name,
                ok=False,
                error="circuit-open",
                attempts=0,
                duration_seconds=0.0,
            )

        async with self._semaphore:
            for attempt in range(1, self.config.retries + 2):
                attempts = attempt
                self._mark_progress()
                try:
                    logger.info(
                        "dispatch: %s attempt %d/%d timeout=%.1fs",
                        agent_name,
                        attempt,
                        self.config.retries + 1,
                        self.config.timeout_seconds,
                    )
                    output = await self._invoke_once(agent_name, prompt, model, metadata)
                    self.circuit.record_success()
                    self.metrics.inc("dispatch_success")
                    self._mark_progress()
                    return DispatchResult(
                        agent_name=agent_name,
                        ok=True,
                        output=output,
                        attempts=attempts,
                        duration_seconds=time.monotonic() - start,
                    )
                except TimeoutError as ex:
                    self.metrics.inc("dispatch_timeout")
                    self.circuit.record_failure()
                    if attempt <= self.config.retries:
                        sleep_s = self.config.backoff_seconds * (2 ** (attempt - 1))
                        logger.warning("dispatch timeout: %s; retrying in %.2fs", agent_name, sleep_s)
                        await asyncio.sleep(sleep_s)
                        continue
                    return DispatchResult(
                        agent_name=agent_name,
                        ok=False,
                        attempts=attempts,
                        duration_seconds=time.monotonic() - start,
                        error=str(ex),
                        timed_out=True,
                    )
                except Exception as ex:  # noqa: BLE001
                    self.metrics.inc("dispatch_failure")
                    self.circuit.record_failure()
                    if attempt <= self.config.retries:
                        sleep_s = self.config.backoff_seconds * (2 ** (attempt - 1))
                        logger.warning("dispatch failure: %s; retrying in %.2fs (%s)", agent_name, sleep_s, ex)
                        await asyncio.sleep(sleep_s)
                        continue
                    return DispatchResult(
                        agent_name=agent_name,
                        ok=False,
                        attempts=attempts,
                        duration_seconds=time.monotonic() - start,
                        error=str(ex),
                    )

    async def run_architect_developer_reviewer(
        self,
        architect_prompt: str,
        developer_prompt_builder: Callable[[DispatchResult], str],
        reviewer_prompt_builder: Callable[[DispatchResult, DispatchResult], str],
        model_map: Optional[Dict[str, str]] = None,
    ) -> WorkflowResult:
        """Run the canonical 3-stage pipeline with non-halting semantics.

        Args:
            architect_prompt: Initial prompt for Software Architect.
            developer_prompt_builder: Function to build developer prompt from architect result.
            reviewer_prompt_builder: Function to build reviewer prompt from both prior results.
            model_map: Optional dict mapping stage names to specific models.

        Returns:
            WorkflowResult with per-stage results and completion status.
        """
        model_map = model_map or {}
        result = WorkflowResult(ok=False)
        started = time.monotonic()

        try:
            arch = await asyncio.wait_for(
                self.dispatch("Software Architect", self._augment_prompt(architect_prompt), model=model_map.get("architect")),
                timeout=self.config.stage_transition_timeout_seconds,
            )
            result.results["architect"] = arch
            if arch.ok:
                result.completed_stages.append("architect")
            else:
                result.failed_stages.append("architect")

            developer_prompt = developer_prompt_builder(arch)
            dev = await asyncio.wait_for(
                self.dispatch("Senior Developer", developer_prompt, model=model_map.get("developer")),
                timeout=self.config.stage_transition_timeout_seconds,
            )
            result.results["developer"] = dev
            if dev.ok:
                result.completed_stages.append("developer")
            else:
                result.failed_stages.append("developer")

            review_prompt = reviewer_prompt_builder(arch, dev)
            review = await asyncio.wait_for(
                self.dispatch("Code Reviewer", review_prompt, model=model_map.get("reviewer")),
                timeout=self.config.stage_transition_timeout_seconds,
            )
            result.results["reviewer"] = review
            if review.ok:
                result.completed_stages.append("reviewer")
            else:
                result.failed_stages.append("reviewer")

            result.ok = len(result.failed_stages) == 0
            self.metrics.inc("workflow_total")
            if result.ok:
                self.metrics.inc("workflow_success")
            else:
                self.metrics.inc("workflow_partial_or_failed")
            return result
        except asyncio.TimeoutError:
            self.metrics.inc("workflow_timeout")
            return WorkflowResult(
                ok=False,
                completed_stages=result.completed_stages,
                failed_stages=result.failed_stages,
                results=result.results,
                error="workflow stage-transition timeout",
            )
        except Exception as ex:  # noqa: BLE001
            self.metrics.inc("workflow_failure")
            return WorkflowResult(
                ok=False,
                completed_stages=result.completed_stages,
                failed_stages=result.failed_stages,
                results=result.results,
                error=str(ex),
            )
        finally:
            elapsed = time.monotonic() - started
            logger.info("workflow finished in %.2fs", elapsed)

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _trim_single_line(text: str, limit: int = 160) -> str:
        line = " ".join((text or "").strip().split())
        if len(line) <= limit:
            return line
        return line[: limit - 3].rstrip() + "..."

    @staticmethod
    def _append_markdown(path: Path, block: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("", encoding="utf-8")
        with path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n" + block.strip() + "\n")

    def _default_routing_state(self) -> Dict[str, Any]:
        return {
            "persistent_mode": "adaptive-score-based",
            "effective_mode": "adaptive-score-based",
            "mode_source": "default",
            "tier_override_scope": "none",
            "tier_override_active": False,
            "updated_at_utc": self._utc_now_iso(),
        }

    def _sanitize_routing_state(self, raw_state: Dict[str, Any]) -> Dict[str, Any]:
        state = self._default_routing_state()

        persistent_mode = raw_state.get("persistent_mode")
        if persistent_mode in self.ALLOWED_PERSISTENT_MODES:
            state["persistent_mode"] = persistent_mode

        effective_mode = raw_state.get("effective_mode")
        if effective_mode in self.ALLOWED_PERSISTENT_MODES:
            state["effective_mode"] = effective_mode
        else:
            state["effective_mode"] = state["persistent_mode"]

        mode_source = raw_state.get("mode_source")
        if isinstance(mode_source, str) and mode_source.strip():
            state["mode_source"] = mode_source.strip()

        override_scope = raw_state.get("tier_override_scope")
        if override_scope in self.ALLOWED_TIER_OVERRIDE_SCOPES:
            state["tier_override_scope"] = override_scope

        override_active = raw_state.get("tier_override_active")
        state["tier_override_active"] = bool(override_active)

        updated_at = raw_state.get("updated_at_utc")
        if isinstance(updated_at, str) and updated_at.strip():
            state["updated_at_utc"] = updated_at.strip()

        return state

    def _load_routing_state(self, workspace_root: Path) -> Dict[str, Any]:
        state_path = workspace_root / self.ROUTING_STATE_FILE
        if not state_path.exists():
            return self._default_routing_state()

        try:
            raw = json.loads(state_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                logger.warning("routing state file is not an object; using defaults")
                return self._default_routing_state()
            return self._sanitize_routing_state(raw)
        except Exception as ex:  # noqa: BLE001
            logger.warning("failed to parse routing state file; using defaults: %s", ex)
            return self._default_routing_state()

    def _save_routing_state(self, workspace_root: Path, state: Dict[str, Any]) -> None:
        state_path = workspace_root / self.ROUTING_STATE_FILE
        state_path.parent.mkdir(parents=True, exist_ok=True)
        sanitized = self._sanitize_routing_state(state)
        sanitized["updated_at_utc"] = self._utc_now_iso()
        state_path.write_text(json.dumps(sanitized, indent=2) + "\n", encoding="utf-8")

    def initialize_workspace_state(self, workspace_root: str) -> Dict[str, Any]:
        """Ensure canonical routing state exists before orchestration/logging cycles.

        If the state file is missing, try seeding from the template under
        .github/agents/templates/state.json. Fall back to defaults when template
        is missing or invalid.
        """
        root = Path(workspace_root).resolve()
        state_path = root / self.ROUTING_STATE_FILE
        if state_path.exists():
            state = self._load_routing_state(root)
            self._save_routing_state(root, state)
            return state

        template_path = root / self.ROUTING_STATE_TEMPLATE_FILE
        if template_path.exists():
            try:
                raw = json.loads(template_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    state = self._sanitize_routing_state(raw)
                    self._save_routing_state(root, state)
                    return state
                logger.warning("routing state template is not an object; using defaults")
            except Exception as ex:  # noqa: BLE001
                logger.warning("failed to parse routing state template; using defaults: %s", ex)

        state = self._default_routing_state()
        self._save_routing_state(root, state)
        return state

    @classmethod
    def _is_low_risk_direct_admin_prompt(cls, prompt: str) -> bool:
        normalized = " ".join((prompt or "").strip().lower().split())
        return normalized in cls.LOW_RISK_DIRECT_ADMIN_PHRASES

    def _resolve_required_wiki_files(
        self,
        logging_profile: str,
        architect_prompt: str,
        workflow_result: WorkflowResult,
    ) -> List[str]:
        profile = (logging_profile or "full").strip().lower()
        if profile not in {"full", "light", "auto"}:
            raise ValueError("logging_profile must be one of: full, light, auto")

        if profile == "full":
            return list(self.REQUIRED_WIKI_FILES)
        if profile == "light":
            return list(self.LIGHT_WIKI_FILES)

        # auto profile: apply light logging only to direct low-risk admin commands.
        is_direct_like = (
            not workflow_result.completed_stages
            and not workflow_result.failed_stages
            and not workflow_result.results
        )
        if is_direct_like and self._is_low_risk_direct_admin_prompt(architect_prompt):
            return list(self.LIGHT_WIKI_FILES)
        return list(self.REQUIRED_WIKI_FILES)

    def _build_cycle_log_blocks(
        self,
        run_id: str,
        architect_prompt: str,
        workflow_result: WorkflowResult,
        routing_state: Dict[str, Any],
    ) -> Dict[str, str]:
        ts = self._utc_now_iso()
        request_type = self._trim_single_line(architect_prompt, 120) or "unspecified-request"
        failed = ", ".join(workflow_result.failed_stages) if workflow_result.failed_stages else "none"
        completed = ", ".join(workflow_result.completed_stages) if workflow_result.completed_stages else "none"
        outcome = "pass" if workflow_result.ok else "revise"
        status = "completed" if workflow_result.ok else "checkpoint"
        backlog_status = "closed" if workflow_result.ok else "open"
        run_token = run_id.lower()
        persistent_mode = routing_state.get("persistent_mode", "adaptive-score-based")
        effective_mode = routing_state.get("effective_mode", persistent_mode)
        mode_source = routing_state.get("mode_source", "default")
        tier_override_scope = routing_state.get("tier_override_scope", "none")
        tier_override_active = str(bool(routing_state.get("tier_override_active", False))).lower()

        return {
            "Behavior-Log.md": (
                f"### OBS-{run_id}\n\n"
                f"- Timestamp (UTC): {ts}\n"
                f"- Request Type: {request_type}\n"
                f"- Subagent: orchestrator-cycle\n"
                f"- Model Selection: selected_model=n/a | task_type=orchestration | criticality=P2\n"
                f"- Routing Mode: persistent={persistent_mode} | effective={effective_mode} | source={mode_source}\n"
                f"- Fallback/Override: fallback_used={'yes' if failed != 'none' else 'no'} | fallback_reason={'stage_failure' if failed != 'none' else 'n/a'} | override_scope={tier_override_scope} | override_active={tier_override_active} | override_phrase=n/a\n"
                f"- Skills Used: prompt-optimizer, orchestrator\n"
                f"- Prompt Normalization: performed\n"
                f"- Contract Score: {'1.0' if workflow_result.ok else '0.6'}\n"
                f"- Outcome: {outcome}\n"
                f"- Failure Mode (if any): {workflow_result.error or failed}\n"
                f"- Root Cause Hypothesis: {'none' if workflow_result.ok else 'provider or prompt quality'}\n"
                f"- Follow-up Action: {'monitor next cycle' if workflow_result.ok else 'open backlog and runbook checkpoint'}\n"
                f"- Related: [Behavior-Patterns](Behavior-Patterns.md#pat-{run_token}), [Learning-Backlog](Learning-Backlog.md#lrn-{run_token})\n"
                f"- Compaction Batch: CB-{run_id}\n\n"
                "---"
            ),
            "Skill-Usage-Log.md": (
                f"### SKL-{run_id}\n\n"
                f"- Timestamp (UTC): {ts}\n"
                f"- Request Type: {request_type}\n"
                f"- Routing Path: multi-agent\n"
                f"- Subagent(s): Software Architect, Senior Developer, Code Reviewer\n"
                f"- Skills Used (ordered): prompt-optimizer, orchestrator-routing, self-improving-log-contract\n"
                f"- Invocation Reason: enforce mandatory orchestration cycle logging\n"
                f"- Outcome Impact: {'positive' if workflow_result.ok else 'neutral'}\n"
                f"- Reuse Note: keep strict wiki log contract enabled for every cycle\n"
                f"- Related: [Behavior-Log](Behavior-Log.md#obs-{run_token}), [Behavior-Patterns](Behavior-Patterns.md#pat-{run_token}), [Learning-Backlog](Learning-Backlog.md#lrn-{run_token})\n\n"
                "---"
            ),
            "Project-Context-Log.md": (
                f"### CTX-{run_id}\n\n"
                f"- Timestamp (UTC): {ts}\n"
                f"- Project/Request: {request_type}\n"
                f"- Stage: {status}\n"
                "- Summary:\n"
                f"  - Completed: {completed}\n"
                f"  - In Progress: {'none' if workflow_result.ok else 'follow-up remediation'}\n"
                f"  - Blockers/Risks: {failed}\n"
                f"  - Next Action: {'continue normal routing' if workflow_result.ok else 'review failed stage and re-run'}\n"
                f"- Routing/Policy Changes: persistent_mode={persistent_mode} | effective_mode={effective_mode} | mode_source={mode_source} | override_scope={tier_override_scope} | override_active={tier_override_active}\n"
                f"- Related: [Behavior-Log](Behavior-Log.md#obs-{run_token}), [Learning-Backlog](Learning-Backlog.md#lrn-{run_token}), [Runbook](Runbook.md#chg-{run_token})\n\n"
                "---"
            ),
            "Behavior-Patterns.md": (
                f"### PAT-{run_id}\n\n"
                f"- Timestamp (UTC): {ts}\n"
                "- Pattern: Orchestration cycle must produce all wiki logs before completion\n"
                f"- Trigger: workflow_result_ok={str(workflow_result.ok).lower()}\n"
                f"- Signal: completed={completed}; failed={failed}\n"
                "- Confidence: medium\n"
                f"- Evidence: [Behavior-Log](Behavior-Log.md#obs-{run_token})\n"
                f"- Action: {'continue policy' if workflow_result.ok else 'prioritize failure remediation'}\n\n"
                "---"
            ),
            "Learning-Backlog.md": (
                f"### LRN-{run_id}\n\n"
                f"- Timestamp (UTC): {ts}\n"
                "- Area: orchestrator-logging-contract\n"
                f"- Title: Verify mandatory log updates for request '{request_type}'\n"
                f"- Priority: {'P3' if workflow_result.ok else 'P2'}\n"
                f"- Status: {backlog_status}\n"
                f"- Trigger: failed_stages={failed}\n"
                f"- Next Action: {'No action required; monitor drift' if workflow_result.ok else 'add targeted retry/fallback improvements for failed stages'}\n"
                f"- Related: [Behavior-Log](Behavior-Log.md#obs-{run_token}), [Runbook](Runbook.md#chg-{run_token})\n\n"
                "---"
            ),
            "Runbook.md": (
                f"### CHG-{run_id}\n\n"
                f"- Timestamp (UTC): {ts}\n"
                "- Change: Completed orchestration cycle with mandatory wiki log contract check\n"
                f"- Scope: completed={completed}; failed={failed}\n"
                f"- Routing State: persistent_mode={persistent_mode}; effective_mode={effective_mode}; mode_source={mode_source}; tier_override_scope={tier_override_scope}; tier_override_active={tier_override_active}\n"
                f"- Expected Effect: {'stable continuity for self-improvement memory' if workflow_result.ok else 'improve resiliency via documented follow-up'}\n"
                "- Rollback: disable strict wiki contract only for emergency troubleshooting\n"
                f"- Related Entries: [Behavior-Patterns](Behavior-Patterns.md#pat-{run_token}), [Learning-Backlog](Learning-Backlog.md#lrn-{run_token})\n\n"
                "---"
            ),
        }

    def enforce_wiki_log_contract(
        self,
        workspace_root: str,
        architect_prompt: str,
        workflow_result: WorkflowResult,
        strict: bool = True,
        logging_profile: str = "full",
    ) -> WikiLogReport:
        """Write and verify required wiki logs for the completed orchestration cycle.

        In strict mode, raises RuntimeError when any required log is not updated.
        """
        root = Path(workspace_root).resolve()
        wiki_root = root / ".wiki" / "orchestrator"
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        routing_state = self.initialize_workspace_state(str(root))

        pre_sizes: Dict[str, int] = {}
        required_files = self._resolve_required_wiki_files(
            logging_profile=logging_profile,
            architect_prompt=architect_prompt,
            workflow_result=workflow_result,
        )
        for rel_name in required_files:
            p = wiki_root / rel_name
            pre_sizes[rel_name] = p.stat().st_size if p.exists() else -1

        blocks = self._build_cycle_log_blocks(run_id, architect_prompt, workflow_result, routing_state)
        write_errors: Dict[str, str] = {}

        for rel_name in required_files:
            p = wiki_root / rel_name
            try:
                self._append_markdown(p, blocks[rel_name])
            except Exception as ex:  # noqa: BLE001
                write_errors[rel_name] = str(ex)

        missing_files: List[str] = []
        unchanged_files: List[str] = []
        updated_files: List[str] = []
        for rel_name in required_files:
            p = wiki_root / rel_name
            if not p.exists():
                missing_files.append(rel_name)
                continue
            if p.stat().st_size > pre_sizes.get(rel_name, -1):
                updated_files.append(rel_name)
            else:
                unchanged_files.append(rel_name)

        ok = not write_errors and not missing_files and not unchanged_files
        report = WikiLogReport(
            ok=ok,
            workspace_root=str(root),
            wiki_root=str(wiki_root),
            required_files=required_files,
            updated_files=updated_files,
            missing_files=missing_files,
            unchanged_files=unchanged_files,
            write_errors=write_errors,
            run_id=run_id,
        )

        if ok:
            self.metrics.inc("wiki_log_contract_pass")
            logger.info("wiki log contract passed: run_id=%s updated=%d", run_id, len(updated_files))
            return report

        self.metrics.inc("wiki_log_contract_fail")
        logger.error(
            "wiki log contract failed: run_id=%s missing=%s unchanged=%s errors=%s",
            run_id,
            missing_files,
            unchanged_files,
            write_errors,
        )
        if strict:
            raise RuntimeError(
                "Wiki log contract violation: required orchestrator logs were not fully updated. "
                f"run_id={run_id} missing={missing_files} unchanged={unchanged_files} errors={write_errors}"
            )
        return report


def start_monitoring_server(runtime: OrchestratorRuntime, host: str = "127.0.0.1", port: int = 9000):
    """Start a lightweight HTTP monitoring server in a background daemon thread."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/metrics":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.end_headers()
                for k, v in sorted(runtime.metrics.snapshot().items()):
                    self.wfile.write(f"{k} {v}\n".encode())
                self.wfile.write(f"circuit_state {runtime.circuit.state}\n".encode())
            elif self.path == "/health":
                status = 200 if runtime.circuit.state != "OPEN" else 503
                body = {
                    "status": "ok" if status == 200 else "degraded",
                    "circuit": runtime.circuit.state,
                }
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, fmt, *args):
            logger.debug("monitor: %s", fmt % args)

    server = HTTPServer((host, port), Handler)

    def serve() -> None:
        logger.info("monitoring server started at http://%s:%d", host, port)
        try:
            server.timeout = 1.0
            while True:
                server.handle_request()
        except (OSError, ValueError):
            pass
        except KeyboardInterrupt:
            pass
        except Exception:  # noqa: BLE001
            logger.debug("monitoring server stopped")
        finally:
            try:
                server.server_close()
            except Exception:  # noqa: BLE001
                pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return server


__all__ = [
    "DispatchConfig",
    "DispatchResult",
    "WorkflowResult",
    "WikiLogReport",
    "SubagentProvider",
    "OrchestratorRuntime",
    "CircuitBreaker",
    "Metrics",
    "start_monitoring_server",
]
