"""Run the planning (Agent 1) or requirements discovery (Agent 2) evaluation.

    python -m omniora_api.evals                 grade the stored candidate outputs (free, deterministic)
    python -m omniora_api.evals --live          generate fresh plans with the configured provider, then grade them
    python -m omniora_api.evals --live --out r.json   also write the full report to a file
    python -m omniora_api.evals --agent requirements [--live] [--out r.json]   the same for discovery turns

`--live` makes real, billed model calls through the same factory and agent code the worker uses
(provider chosen by OMNIORA_MODEL_PROVIDER). It is never run by the test suite. Run it from
`backend/` so `backend/.env` is read. Fixtures that only exercise the validators (invalid output,
cyclic dependencies) have no planning input worth sending to a model and are reported as
"not applicable" in live mode, never as live passes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..agents.project_manager import PlanningInput, run_project_manager
from ..agents.requirements_analyst import run_requirements_analyst
from ..config import get_settings
from ..llm.factory import build_planning_provider
from .discovery import grade_discovery, load_discovery_fixtures
from .graders import grade, load_fixtures


def _attempt_summary(record) -> dict[str, Any]:
    return {
        "attempt": record.attempt,
        "outcome": record.outcome,
        "model": record.model,
        "input_tokens": record.input_tokens,
        "output_tokens": record.output_tokens,
        "latency_ms": record.latency_ms,
        "error_code": record.error_code,
        "error_message": record.error_message,
        "validation_errors": record.validation_errors[:10],
    }


def _discovery_entries(settings, provider, only: str | None = None) -> list[dict[str, Any]]:
    entries = []
    for fixture in load_discovery_fixtures():
        if only and fixture.name != only:
            continue
        entry: dict[str, Any] = {"fixture": fixture.name}
        if provider is None:
            graded = grade_discovery(fixture)
            entry.update(
                source=fixture.candidate_source, passed=graded.passed, checks=graded.checks, problems=graded.problems
            )
        elif not fixture.expect["valid"]:
            entry.update(source="validator fixture", passed=None, status="not applicable in live mode")
        else:
            print(f"[live] {fixture.name} ...", file=sys.stderr, flush=True)
            result = run_requirements_analyst(
                provider,
                fixture.discovery,
                max_attempts=settings.analyst_max_attempts,
                max_output_tokens=settings.analyst_output_tokens,
                request_token_budget=settings.analyst_token_budget,
                effort=settings.planning_effort,
                timeout_seconds=settings.model_timeout_seconds,
            )
            accepted = result.output is not None
            output = (
                result.output.model_dump_json()
                if accepted
                else next((a.raw_output for a in reversed(result.attempts) if a.raw_output), "")
            )
            graded = grade_discovery(fixture, output)
            entry.update(
                source="live",
                output_accepted=accepted,
                failure_code=result.failure_code,
                attempts=[_attempt_summary(a) for a in result.attempts],
                input_tokens=sum(a.input_tokens or 0 for a in result.attempts),
                output_tokens=sum(a.output_tokens or 0 for a in result.attempts),
                passed=graded.passed,
                checks=graded.checks,
                problems=graded.problems[:10],
                document=result.turn.document.model_dump(mode="json") if result.turn and result.turn.document else None,
                questions=[q.model_dump(mode="json") for q in result.output.questions] if accepted else None,
            )
        entries.append(entry)
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="generate outputs with the configured model provider")
    parser.add_argument("--agent", choices=["planning", "requirements"], default="planning")
    parser.add_argument("--out", type=Path, help="write the JSON report to this file")
    parser.add_argument("--fixture", help="run only the fixture with this name (for a targeted live re-check)")
    args = parser.parse_args()

    settings = get_settings() if args.live else None
    provider = build_planning_provider(settings) if settings else None
    if provider is not None and not provider.configured:
        print(f"The selected provider ({settings.model_provider}) has no API key configured.", file=sys.stderr)
        return 2

    report: dict[str, Any] = {
        "agent": args.agent,
        "mode": "live" if args.live else "stored-candidates",
        "fixtures": [],
    }
    if provider is not None:
        requirements = args.agent == "requirements"
        report.update(
            provider=provider.name,
            model=provider.model,
            effort=settings.planning_effort,
            max_output_tokens=settings.analyst_output_tokens if requirements else settings.planning_max_output_tokens,
            max_attempts=settings.analyst_max_attempts if requirements else settings.pm_max_attempts,
        )

    planning_fixtures = load_fixtures() if args.agent == "planning" else []
    if args.fixture:
        planning_fixtures = [f for f in planning_fixtures if f.name == args.fixture]
    if args.agent == "requirements":
        report["fixtures"] = _discovery_entries(settings, provider, args.fixture)

    for fixture in planning_fixtures:
        entry: dict[str, Any] = {"fixture": fixture.name}
        if provider is None:
            graded = grade(fixture)
            entry.update(
                source=fixture.candidate_source, passed=graded.passed, checks=graded.checks, problems=graded.problems
            )
        elif not fixture.expect["valid"]:
            entry.update(source="validator fixture", passed=None, status="not applicable in live mode")
        else:
            print(f"[live] {fixture.name} ...", file=sys.stderr, flush=True)
            result = run_project_manager(
                provider,
                PlanningInput(configuration=fixture.configuration, notes=fixture.notes),
                max_attempts=settings.pm_max_attempts,
                max_output_tokens=settings.planning_max_output_tokens,
                effort=settings.planning_effort,
                timeout_seconds=settings.model_timeout_seconds,
            )
            # Grade the plan the production path accepted; if none was accepted, grade the last output.
            output = (
                result.plan.model_dump_json()
                if result.plan is not None
                else next((a.raw_output for a in reversed(result.attempts) if a.raw_output), "")
            )
            graded = grade(fixture, output)
            entry.update(
                source="live",
                plan_accepted=result.plan is not None,
                failure_code=result.failure_code,
                attempts=[_attempt_summary(a) for a in result.attempts],
                input_tokens=sum(a.input_tokens or 0 for a in result.attempts),
                output_tokens=sum(a.output_tokens or 0 for a in result.attempts),
                passed=graded.passed,
                checks=graded.checks,
                problems=graded.problems[:10],
                # Kept so a failed check can be inspected against what the model actually wrote.
                plan=result.plan.model_dump(mode="json") if result.plan is not None else None,
            )
        report["fixtures"].append(entry)

    graded_entries = [e for e in report["fixtures"] if e["passed"] is not None]
    passed = sum(bool(e["passed"]) for e in graded_entries)
    report["summary"] = {
        "graded": len(graded_entries),
        "passed": passed,
        "not_applicable": len(report["fixtures"]) - len(graded_entries),
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(f"{passed}/{len(graded_entries)} graded fixtures passed", file=sys.stderr)
    return 0 if passed == len(graded_entries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
