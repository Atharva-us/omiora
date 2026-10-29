"""Pure domain rules: ids, project rules (parity with the frontend), and the run state machine."""

from __future__ import annotations

import itertools

import pytest
from pydantic import ValidationError

from omniora_api.domain.projects import (
    CustomStack,
    ProjectConfiguration,
    configuration_problems,
    normalize_configuration,
    validate_note,
    validate_project_name,
    validate_stack,
)
from omniora_api.domain.runs import TERMINAL_STATES, TRANSITIONS, RunState, can_transition
from omniora_api.ids import uuid7

from .support import configuration


class TestUuid7:
    def test_version_and_variant(self) -> None:
        value = uuid7()
        assert value.version == 7
        assert value.variant == "specified in RFC 4122"

    def test_monotonic_within_a_process(self) -> None:
        ids = [uuid7() for _ in range(5000)]
        assert ids == sorted(ids)
        assert len(set(ids)) == len(ids)


class TestProjectRules:
    # These messages and outcomes mirror src/domain/projects/*.test.ts.
    def test_rejects_overlapping_frameworks(self) -> None:
        result = validate_stack("website", CustomStack(mode="custom", technologies=["react", "nextjs"]))
        assert any("React and Next.js" in error for error in result.errors)

    def test_requires_client_and_server_layers(self) -> None:
        assert (
            "A website needs a web client. Add React, Next.js, or Flutter (web)."
            in validate_stack("website", CustomStack(mode="custom", technologies=["react-native"])).errors
        )
        assert (
            "PostgreSQL needs a server layer. Add FastAPI, Node.js, or Next.js."
            in validate_stack("website", CustomStack(mode="custom", technologies=["react", "postgresql"])).errors
        )
        assert validate_stack("both", CustomStack(mode="custom", technologies=["flutter"])).errors == []

    def test_name_and_note_limits_apply_after_trimming(self) -> None:
        assert validate_project_name("  " + "a" * 80 + "  ") is None
        assert validate_project_name("a" * 81) == "Use 80 characters or fewer."
        assert validate_note("   ") == "Write a note before adding it."

    def test_configuration_problems_and_normalisation(self) -> None:
        config = ProjectConfiguration.model_validate(
            configuration(name="  Spaced ", stack={"mode": "custom", "technologies": ["react", "react"]})
        )
        normalized = normalize_configuration(config)
        assert normalized.name == "Spaced"
        assert normalized.stack == CustomStack(mode="custom", technologies=["react"])
        assert configuration_problems(normalized) == []
        bad = ProjectConfiguration.model_validate(configuration(name="", referenceUrl="javascript:alert(1)"))
        assert configuration_problems(bad) == [
            "Give your project a name.",
            "Enter a full URL starting with http:// or https://.",
        ]

    def test_schema_rejects_unknown_values_and_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ProjectConfiguration.model_validate(configuration(stack={"mode": "custom", "technologies": ["cobol"]}))
        with pytest.raises(ValidationError):
            ProjectConfiguration.model_validate(configuration(stack={"mode": "recommend", "technologies": []}))
        with pytest.raises(ValidationError):
            ProjectConfiguration.model_validate({**configuration(), "owner": "someone-else"})


class TestRunStateMachine:
    def test_terminal_states_have_no_exits(self) -> None:
        for state in TERMINAL_STATES:
            assert TRANSITIONS[state] == frozenset()

    def test_approval_never_leads_to_execution(self) -> None:
        assert not any(can_transition(RunState.APPROVED, target) for target in RunState)

    @pytest.mark.parametrize(("current", "target"), list(itertools.product(RunState, RunState)))
    def test_every_pair_matches_the_table(self, current: RunState, target: RunState) -> None:
        assert can_transition(current, target) == (target in TRANSITIONS[current])

    def test_expected_paths(self) -> None:
        assert can_transition(RunState.QUEUED, RunState.PLANNING)
        assert can_transition(RunState.PLANNING, RunState.AWAITING_APPROVAL)
        assert can_transition(RunState.AWAITING_APPROVAL, RunState.QUEUED)  # revision
        assert not can_transition(RunState.PLANNING, RunState.APPROVED)  # approval needs a human
        assert not can_transition(RunState.QUEUED, RunState.AWAITING_APPROVAL)
