"""Provider adapters for different LLM backends (Claude, Copilot, Mock)."""

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("orchestrator.providers")


class MockProvider:
    """Mock provider for testing and local validation."""

    def __init__(self, behavior: Optional[Dict[str, Any]] = None):
        """
        Args:
            behavior: Dict mapping agent_name to {"delay": float, "payload": str, "fail": bool}.
        """
        self.behavior = behavior or {}

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Simulate a subagent call."""
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


class ClaudeProvider:
    """Provider for Claude API calls."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-sonnet-20240229"):
        """
        Args:
            api_key: Anthropic API key (or use env var ANTHROPIC_API_KEY).
            model: Claude model identifier.
        """
        self.api_key = api_key
        self.model = model
        self._client = None

    @property
    def client(self):
        """Lazy-load Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise ImportError("Install anthropic package: pip install anthropic") from e
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Call Claude with the prompt."""
        model = model or self.model
        system_prompt = f"You are a {agent_name}."
        if metadata and "system" in metadata:
            system_prompt = metadata["system"]

        # Run sync Claude call in executor to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(
                model=model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return response.content[0].text


class CopilotProvider:
    """Provider stub for GitHub Copilot.
    
    NOTE: This is a reference design. Actual integration depends on your
    Copilot orchestration layer and how you expose runSubagent.
    """

    def __init__(self, base_url: str = "http://localhost:3000", timeout: float = 45.0):
        """
        Args:
            base_url: URL to your Copilot orchestration service.
            timeout: HTTP request timeout.
        """
        self.base_url = base_url
        self.timeout = timeout

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Call Copilot orchestration endpoint.
        
        Assumes your Copilot service has an HTTP endpoint like:
        POST /invoke
        Body: {"agent": "Software Architect", "prompt": "...", "model": "gpt-4"}
        Response: {"output": "..."}
        """
        import aiohttp

        payload = {
            "agent": agent_name,
            "prompt": prompt,
            "model": model or "auto",
        }
        if metadata:
            payload["metadata"] = metadata

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/invoke",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Copilot service error: {resp.status}")
                data = await resp.json()
                return data.get("output", "")


class HttpProvider:
    """Generic HTTP provider for custom backends.
    
    Useful for self-hosted or third-party LLM services.
    """

    def __init__(self, endpoint: str, timeout: float = 45.0):
        """
        Args:
            endpoint: HTTP endpoint URL (POST).
            timeout: Request timeout in seconds.

        Expected response format:
        {"output": "..."}
        """
        self.endpoint = endpoint
        self.timeout = timeout

    async def invoke(
        self,
        agent_name: str,
        prompt: str,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Call the HTTP endpoint."""
        import aiohttp

        payload = {
            "agent": agent_name,
            "prompt": prompt,
            "model": model,
        }
        if metadata:
            payload.update(metadata)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.endpoint,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP provider error: {resp.status} {await resp.text()}")
                data = await resp.json()
                return data.get("output", "")


__all__ = [
    "MockProvider",
    "ClaudeProvider",
    "CopilotProvider",
    "HttpProvider",
]
