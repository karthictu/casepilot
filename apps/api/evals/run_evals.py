"""Offline routing eval: runs each case in routing.yaml through the orchestrator and gates on accuracy.

uv run python evals/run_evals.py            # mock LLM (deterministic, CI)
CASEPILOT_LLM_PROVIDER=litellm CASEPILOT_MODEL_INTENT=openai/gpt-4o-mini uv run python evals/run_evals.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from app.agents.orchestrator import run_orchestrator  # noqa: E402
from app.agents.plugin import load_plugins  # noqa: E402


async def main() -> int:
    spec = yaml.safe_load((Path(__file__).parent / "routing.yaml").read_text())
    load_plugins()
    rows, passed = [], 0
    for case in spec["cases"]:
        decision = await run_orchestrator(case["query"])
        ok = decision["intent"] == case["intent"] and decision["route_to"] == case["route_to"]
        passed += ok
        rows.append(
            {
                "query": case["query"],
                "expected": case["intent"],
                "got": decision["intent"],
                "route_to": decision["route_to"],
                "confidence": decision["confidence"],
                "pass": ok,
            }
        )
    accuracy = passed / len(rows)
    for r in rows:
        print(f"{'PASS' if r['pass'] else 'FAIL'}  {r['expected']:<20} got={r['got']:<20} {r['query']}")
    print(
        json.dumps(
            {"cases": len(rows), "passed": passed, "accuracy": round(accuracy, 3), "threshold": spec["threshold"]}
        )
    )
    return 0 if accuracy >= spec["threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
