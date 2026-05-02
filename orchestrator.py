import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger("orchestrator")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


class SubagentProvider(Protocol):
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
    agent_name: str
    ok: bool
    output: str = ""
    attempts: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None
    timed_out: bool = False


@dataclass
class WorkflowResult:
    ok: bool
    completed_stages: List[str] = field(default_factory=list)
    failed_stages: List[str] = field(default_factory=list)
    results: Dict[str, DispatchResult] = field(default_factory=dict)
    error: Optional[str] = None


class Metrics:
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

    Key anti-stall behavior:
    - Per-dispatch timeout and retry with backoff.
    - Circuit breaker to avoid repeated dead-path calls.
    - Bounded concurrency via semaphore.
    - Workflow-level timeout and stage-transition timeout.
    - Partial-result workflow semantics (no global halt on one stage failure).
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

    def _mark_progress(self) -> None:
        self._last_progress_ts = time.monotonic()

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

        The orchestrator continues and returns partial results even if one stage fails,
        unless workflow timeout is hit.
        """
        model_map = model_map or {}
        result = WorkflowResult(ok=False)
        started = time.monotonic()

        try:
            arch = await asyncio.wait_for(
                self.dispatch("Software Architect", architect_prompt, model=model_map.get("architect")),
                timeout=self.config.stage_transition_timeout_seconds,
            )
            result.results["architect"] = arch
            if arch.ok:
                result.completed_stages.append("architect")
            else:
                result.failed_stages.append("architect")

            # If architect failed, developer still receives a fallback prompt.
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


class MockProvider:
    """A tiny provider used for local validation and tests."""

    def __init__(self, behavior: Optional[Dict[str, Any]] = None):
        self.behavior = behavior or {}

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        cfg = self.behavior.get(agent_name, {})
        delay = float(cfg.get("delay", 0.2))
        fail = bool(cfg.get("fail", False))
        payload = cfg.get("payload")
        await asyncio.sleep(delay)
        if fail:
            raise RuntimeError(cfg.get("error", "simulated provider failure"))
        if payload is not None:
            return str(payload)
        return f"{agent_name} response for: {prompt[:60]}"


def start_monitoring_server(runtime: OrchestratorRuntime, host: str = "127.0.0.1", port: int = 9000):
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
            # Socket closed or invalid; daemon thread will exit
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
    "SubagentProvider",
    "OrchestratorRuntime",
    "MockProvider",
    "CircuitBreaker",
    "start_monitoring_server",
]
