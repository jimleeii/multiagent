#!/usr/bin/env python3
"""Compatibility wrapper for the canonical orchestrator demo runner."""

from pathlib import Path
import sys

_AGENTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "agents"
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from orchestrator.demo_run import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
