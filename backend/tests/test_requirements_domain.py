"""Requirements Analyst contract: schemas, id assignment, versioning, validation, and state machines.
Pure functions only: no database and no model calls."""

from __future__ import annotations

import itertools
from typing import ClassVar

import pytest
from pydantic import ValidationError

from omniora_api.domain.plans import ProjectPlan, plan_problems
from omniora_api.domain.projects import ProjectConfiguration
from omniora_api.domain.requirements import (
    AnalystTurnOutput,
    ApprovedRequirements,
    QuestionState,
    Requirement,
    RequirementsDocument,
    TurnContext,
    analyst_output_schema,
    content_sha256,
    evaluate_turn,
    readiness_blockers,
)
from omniora_api.domain.runs import (
    DISCOVERY_TRANSITIONS,
    PLANNING_TRANSITIONS,
    AgentRole,
    RunState,
    can_transition,
)

from .support import analyst_context, analyst_output, configuration, plan, question, requirement_op


def output(**overrides) -> AnalystTurnOutput:
    return AnalystTurnOutput.model_validate(analyst_output(**overrides))


def asked(key: str = "DQ-001", **overrides) -> QuestionState:
    values = {
        "key": key,
        "prompt": "Which payment methods must checkout accept?",
        "kind": "multiple-choice",
        "options": ("Cards", "PayPal"),
        "blocking": True,
        "topic": "scope",
        "status": "open",
    }
    values.update(overrides)
    return QuestionState(**values)


def first_turn(out: AnalystTurnOutput, questions: tuple[QuestionState, ...] = (), notes: int = 0, **kwargs):
    context = TurnContext(previous=None, questions=questions, note_count=notes, **kwargs)
    return evaluate_turn(out, context, first_question_number=len(questions) + 1)


def document(*requirements: Requirement, tenancy: str = "single", **overrides) -> RequirementsDocument:
    values = {
        "context": analyst_context(tenancy=tenancy),
        "requirements": list(requirements),
        "assumptions": [],
        "open_questions": [],
        "readiness": {"ready": False, "blockers": []},
        "decisions": [],
    }
    values.update(overrides)
    return RequirementsDocument.model_validate(values)


def requirement(rid: str = "REQ-001", **overrides) -> Requirement:
    values = requirement_op(id=rid)
    values.pop("op")
    values.pop("reason")
    values.update({"status": "active", **overrides})
    return Requirement.model_validate(values)


def next_turn(previous: RequirementsDocument, out: AnalystTurnOutput, questions=(), **kwargs):
    context = TurnContext(previous=previous, questions=tuple(questions), note_count=0, **kwargs)
    return evaluate_turn(out, context, first_question_number=len(questions) + 1)


class TestSchemas:
    def test_valid_output_builds_a_version_with_server_ids_and_question_snapshot(self) -> None:
        result = first_turn(output(operations=[requirement_op(), requirement_op(statement="Shoppers can pay.")]))
        assert result.problems == []
        assert [r.id for r in result.document.requirements] == ["REQ-001", "REQ-002"]
        assert [q.key for q in result.questions] == ["DQ-001"]
        assert result.document.open_questions[0].key == "DQ-001" and result.document.readiness.ready is False

    def test_shape_limits(self) -> None:
        with pytest.raises(ValidationError, match="questions"):
            output(questions=[question(prompt=f"Question {n}?") for n in range(6)])  # at most five per turn
        with pytest.raises(ValidationError):
            AnalystTurnOutput.model_validate({**analyst_output(), "surprise": True})
        with pytest.raises(ValidationError):
            requirement("R1")  # ids are REQ-NNN
        with pytest.raises(ValidationError):
            requirement(acceptance_criteria=[])

    def test_structured_output_schema_is_strict_everywhere(self) -> None:
        def walk(node: dict) -> None:
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
                for child in node["properties"].values():
                    walk(child)
            if node.get("type") == "array":
                walk(node["items"])

        walk(analyst_output_schema())

    def test_content_hash_is_canonical(self) -> None:
        one = document(requirement())
        same = RequirementsDocument.model_validate(one.model_dump(mode="json"))
        assert content_sha256(one) == content_sha256(same)
        changed = document(requirement(statement="Different."))
        assert content_sha256(one) != content_sha256(changed)


class TestIdsAndVersions:
    def test_updates_keep_ids_deprecations_keep_rows_and_numbers_are_never_reused(self) -> None:
        base = document(requirement("REQ-001"), requirement("REQ-002", priority="should"))
        result = next_turn(
            base,
            output(
                operations=[
                    requirement_op(op="update", id="REQ-001", statement="Shoppers can browse and search."),
                    requirement_op(op="deprecate", id="REQ-002", reason="Out of scope for launch."),
                    requirement_op(statement="Shoppers can save favourites."),
                ]
            ),
        )
        assert result.problems == []
        by_id = {r.id: r for r in result.document.requirements}
        assert by_id["REQ-001"].statement == "Shoppers can browse and search."
        assert by_id["REQ-002"].status == "deprecated" and by_id["REQ-002"].deprecation_reason
        assert "REQ-003" in by_id  # next number after the highest ever used

        later = next_turn(result.document, output(operations=[requirement_op(statement="Gift wrapping.")]))
        assert [r.id for r in later.document.requirements][-1] == "REQ-004"
        assert len(later.document.requirements) == 4  # nothing is ever removed

    @pytest.mark.parametrize(
        ("op", "message"),
        [
            (requirement_op(id="REQ-009"), "leave id empty"),
            (requirement_op(op="update", id="REQ-404"), "unknown requirement id"),
            (requirement_op(op="deprecate", id="REQ-002", reason=""), "give a reason"),
        ],
    )
    def test_model_cannot_assign_or_invent_ids(self, op, message) -> None:
        base = document(requirement("REQ-001"), requirement("REQ-002", priority="should"))
        assert any(message in p for p in next_turn(base, output(operations=[op])).problems)

    def test_duplicate_and_deprecated_targets_are_rejected(self) -> None:
        base = document(requirement("REQ-001"), requirement("REQ-002", status="deprecated", priority="could"))
        twice = next_turn(
            base,
            output(operations=[requirement_op(op="update", id="REQ-001"), requirement_op(op="update", id="REQ-001")]),
        )
        assert any("more than one operation" in p for p in twice.problems)
        revived = next_turn(base, output(operations=[requirement_op(op="update", id="REQ-002")]))
        assert any("deprecated" in p for p in revived.problems)


class TestEvidence:
    def test_cannot_cite_an_answer_that_was_never_submitted(self) -> None:
        result = first_turn(
            output(operations=[requirement_op(source="answer", evidence=["answer:DQ-001"])]), questions=(asked(),)
        )
        assert any("no answer to DQ-001 has been submitted" in p for p in result.problems)

    def test_i_dont_know_is_not_a_fact(self) -> None:
        unknown = asked(status="answered", unknown=True)
        as_fact = first_turn(
            output(operations=[requirement_op(source="answer", evidence=["answer:DQ-001"])]), questions=(unknown,)
        )
        assert any("I don't know" in p for p in as_fact.problems)

    def test_user_attribution_needs_matching_evidence(self) -> None:
        invented = first_turn(output(operations=[requirement_op(source="answer", evidence=[])]))
        assert any("do not attribute it to the user" in p for p in invented.problems)
        bad_field = first_turn(output(operations=[requirement_op(evidence=["brief:budget"])]))
        assert any("unknown brief field" in p for p in bad_field.problems)
        no_note = first_turn(output(operations=[requirement_op(source="note", evidence=["note:2"])]), notes=1)
        assert any("1 note(s)" in p for p in no_note.problems)
        answered = asked(status="answered")
        good = first_turn(
            output(
                operations=[requirement_op(source="answer", evidence=["answer:DQ-001"])],
                questions=[],
                readiness={"ready": True, "blockers": []},
            ),
            questions=(answered,),
        )
        assert good.problems == []

    def test_inferred_requirements_cannot_claim_high_confidence(self) -> None:
        result = first_turn(output(operations=[requirement_op(source="inferred", evidence=[], confidence="high")]))
        assert any("high confidence" in p for p in result.problems)
        ok = first_turn(output(operations=[requirement_op(source="inferred", evidence=[], confidence="medium")]))
        assert ok.problems == []

    def test_must_haves_cannot_be_silently_weakened(self) -> None:
        base = document(requirement("REQ-001"))
        lowered = next_turn(base, output(operations=[requirement_op(op="update", id="REQ-001", priority="could")]))
        assert any("must-have" in p for p in lowered.problems)
        dropped = next_turn(
            base, output(operations=[requirement_op(op="deprecate", id="REQ-001", reason="Not needed")])
        )
        assert any("must-have" in p for p in dropped.problems)
        user_said_so = next_turn(
            base,
            output(
                operations=[
                    requirement_op(
                        op="deprecate",
                        id="REQ-001",
                        reason="The user said this is out of scope.",
                        evidence=["answer:DQ-001"],
                    ),
                    requirement_op(statement="Shoppers can pay by card."),
                ],
                questions=[],
                readiness={"ready": True, "blockers": []},
            ),
            questions=[asked(status="answered")],
        )
        assert user_said_so.problems == []


class TestQuestions:
    def test_question_rules(self) -> None:
        repeat = first_turn(output(questions=[question()]), questions=(asked(status="answered"),))
        assert any("repeats DQ-001" in p for p in repeat.problems)
        no_options = first_turn(output(questions=[question(options=["Cards"])]))
        assert any("at least two distinct" in p for p in no_options.problems)
        stray = first_turn(output(questions=[question(kind="free-text")]))
        assert any("take no options" in p for p in stray.problems)
        final = first_turn(output(), final_turn=True)
        assert any("final discovery turn" in p for p in final.problems)
        withdraw = first_turn(output(withdraw_questions=["DQ-001"]), questions=(asked(status="answered"),))
        assert any("not an open question" in p for p in withdraw.problems)

    def test_assumptions_for_unknown_answers_are_qualified(self) -> None:
        unknown = (asked(status="answered", unknown=True),)
        confident = first_turn(
            output(
                questions=[], assumptions=[{"statement": "Cards only.", "confidence": "medium", "basis": ["DQ-001"]}]
            ),
            questions=unknown,
        )
        assert any("confidence must be low" in p for p in confident.problems)


class TestReadiness:
    ready: ClassVar[dict] = {"ready": True, "blockers": []}

    def test_cannot_be_ready_with_an_open_blocking_question(self) -> None:
        result = first_turn(output(readiness=self.ready))
        assert any("Blocking question DQ-001 is unanswered" in p for p in result.problems)

    def test_unknown_blocking_answer_needs_a_recorded_assumption(self) -> None:
        unknown = (asked(status="answered", unknown=True),)
        bare = first_turn(output(questions=[], readiness=self.ready), questions=unknown)
        assert any("no assumption records" in p for p in bare.problems)
        qualified = first_turn(
            output(
                questions=[],
                readiness=self.ready,
                assumptions=[{"statement": "Accept cards first.", "confidence": "low", "basis": ["DQ-001"]}],
            ),
            questions=unknown,
        )
        assert qualified.problems == [] and qualified.document.readiness.ready is True
        assert qualified.document.open_questions[0].status == "unknown"  # still visible for review

    def test_conservative_not_ready_is_accepted_and_blockers_are_reported(self) -> None:
        result = first_turn(output())
        assert result.problems == [] and not result.document.readiness.ready
        assert any("DQ-001" in b for b in result.document.readiness.blockers)

    def test_needs_a_must_have(self) -> None:
        result = first_turn(output(operations=[requirement_op(priority="should")], questions=[], readiness=self.ready))
        assert any("no active must-have" in p for p in result.problems)


class TestTenancy:
    def isolation(self, **overrides):
        return requirement_op(
            statement="Each workspace's data is visible only to its members.",
            kind="non-functional",
            source="inferred",
            confidence="medium",
            evidence=[],
            tags=["tenant-isolation", "security"],
            acceptance_criteria=["A member of workspace A receives 404 for any record of workspace B."],
            **overrides,
        )

    def test_multi_tenant_requires_a_mandatory_isolation_requirement(self) -> None:
        missing = first_turn(output(context=analyst_context(tenancy="multi")))
        assert any("tenant-isolation" in p for p in missing.problems)
        optional = first_turn(
            output(
                context=analyst_context(tenancy="multi"),
                operations=[requirement_op(), self.isolation(priority="should")],
            )
        )
        assert any("tenant-isolation" in p for p in optional.problems)
        present = first_turn(
            output(context=analyst_context(tenancy="multi"), operations=[requirement_op(), self.isolation()])
        )
        assert present.problems == []

    def test_isolation_requirement_cannot_be_deprecated_while_multi_tenant(self) -> None:
        first = first_turn(
            output(context=analyst_context(tenancy="multi"), operations=[requirement_op(), self.isolation()])
        )
        later = next_turn(
            first.document,
            output(
                context=analyst_context(tenancy="multi"),
                operations=[
                    requirement_op(op="deprecate", id="REQ-002", reason="Simplify", evidence=["answer:DQ-001"])
                ],
                questions=[],
            ),
            questions=[asked(status="answered")],
        )
        assert any("tenant-isolation" in p for p in later.problems)

    def test_unknown_tenancy_requires_a_blocking_tenancy_question(self) -> None:
        silent = first_turn(output(context=analyst_context(tenancy="unknown")))
        assert any("topic 'tenancy'" in p for p in silent.problems)
        asks = first_turn(
            output(
                context=analyst_context(tenancy="unknown"),
                questions=[
                    question(
                        prompt="Will separate companies share one deployment?",
                        kind="yes-no",
                        options=[],
                        topic="tenancy",
                    )
                ],
            )
        )
        assert asks.problems == []
        assert any("tenancy model is still unknown" in b for b in asks.document.readiness.blockers)

    def test_readiness_blockers_for_a_stored_document(self) -> None:
        doc = document(requirement(), tenancy="multi")
        assert any("tenant-isolation" in b for b in readiness_blockers(doc, ()))


class TestStateMachines:
    def test_discovery_lifecycle(self) -> None:
        role = AgentRole.REQUIREMENTS_ANALYST
        path = [
            RunState.QUEUED,
            RunState.DISCOVERING,
            RunState.READY_FOR_REVIEW,
            RunState.AWAITING_APPROVAL,
            RunState.NEEDS_CHANGES,
            RunState.DISCOVERING,
            RunState.READY_FOR_REVIEW,
            RunState.AWAITING_APPROVAL,
            RunState.APPROVED,
        ]
        assert all(can_transition(a, b, role) for a, b in itertools.pairwise(path))
        assert can_transition(RunState.READY_FOR_REVIEW, RunState.DISCOVERING, role)  # more questions
        assert not can_transition(RunState.DISCOVERING, RunState.AWAITING_APPROVAL, role)  # must be reviewed first
        assert not can_transition(RunState.AWAITING_APPROVAL, RunState.REJECTED, role)
        assert not can_transition(RunState.APPROVED, RunState.DISCOVERING, role)  # approved versions are final
        for state in (RunState.QUEUED, RunState.DISCOVERING, RunState.READY_FOR_REVIEW, RunState.NEEDS_CHANGES):
            assert can_transition(state, RunState.CANCELLED, role)

    def test_machines_are_separate(self) -> None:
        assert not can_transition(RunState.QUEUED, RunState.DISCOVERING)  # default role: Project Manager
        assert not can_transition(RunState.QUEUED, RunState.PLANNING, AgentRole.REQUIREMENTS_ANALYST)
        for table in (DISCOVERY_TRANSITIONS, PLANNING_TRANSITIONS):
            assert set(table) == set(RunState)  # total: every state has an entry
        assert not DISCOVERY_TRANSITIONS[RunState.PLANNING] and not PLANNING_TRANSITIONS[RunState.DISCOVERING]
        assert not any(RunState.PLANNING in targets for targets in DISCOVERY_TRANSITIONS.values())


class TestPlanHandoff:
    def approved(self) -> ApprovedRequirements:
        doc = document(
            requirement("REQ-001"),
            requirement("REQ-002", priority="should"),
            requirement("REQ-003", status="deprecated", priority="could"),
            requirement("REQ-004", tags=["tenant-isolation"]),
            tenancy="multi",
        )
        return ApprovedRequirements(version_id="v", version=1, content_sha256=content_sha256(doc), document=doc)

    def pinned_plan(self, **overrides) -> ProjectPlan:
        base = plan(
            requirements=[],
            tasks=[
                {
                    "key": "T1",
                    "title": "Catalogue",
                    "description": "Pages.",
                    "acceptance_criteria": ["Renders"],
                    "depends_on": [],
                    "requirement_ids": ["REQ-001", "REQ-002"],
                    "suggested_agent": "frontend-engineer",
                },
                {
                    "key": "T2",
                    "title": "Workspace isolation",
                    "description": "Row-level policies.",
                    "acceptance_criteria": ["Cross-workspace reads return 404"],
                    "depends_on": ["T1"],
                    "requirement_ids": ["REQ-004"],
                    "suggested_agent": "database-engineer",
                },
            ],
        )
        base.update(overrides)
        return ProjectPlan.model_validate(base)

    def problems(self, candidate: ProjectPlan) -> list[str]:
        return plan_problems(candidate, ProjectConfiguration.model_validate(configuration()), self.approved())

    def test_plan_that_references_approved_ids_is_accepted(self) -> None:
        assert self.problems(self.pinned_plan()) == []

    def test_must_haves_are_covered_or_flagged(self) -> None:
        candidate = self.pinned_plan()
        candidate.tasks[1].requirement_ids = ["REQ-002"]
        assert any("'REQ-004' is neither covered" in p for p in self.problems(candidate))
        flagged = ProjectPlan.model_validate(
            {**candidate.model_dump(), "flagged_requirements": [{"id": "REQ-004", "reason": "Deferred to review."}]}
        )
        assert self.problems(flagged) == []

    def test_restating_unknown_and_deprecated_ids_are_rejected(self) -> None:
        restated = self.pinned_plan(
            requirements=[
                {"id": "REQ-001", "statement": "Browse.", "kind": "functional", "priority": "could", "source": "user"}
            ]
        )
        assert any("must not restate approved requirements (REQ-001)" in p for p in self.problems(restated))
        candidate = self.pinned_plan()
        candidate.tasks[0].requirement_ids = ["REQ-001", "REQ-099", "REQ-003"]
        found = self.problems(candidate)
        assert any("unknown requirement 'REQ-099'" in p for p in found)
        assert any("deprecated requirement 'REQ-003'" in p for p in found)
        bogus_flag = self.pinned_plan(flagged_requirements=[{"id": "REQ-777", "reason": "x"}])
        assert any("not an active approved requirement" in p for p in self.problems(bogus_flag))

    def test_derived_requirements_use_their_own_namespace(self) -> None:
        derived = self.pinned_plan(
            requirements=[
                {
                    "id": "D1",
                    "statement": "Audit logging.",
                    "kind": "non-functional",
                    "priority": "should",
                    "source": "inferred",
                }
            ]
        )
        derived.tasks[0].requirement_ids.append("D1")
        assert self.problems(derived) == []
        claimed = self.pinned_plan(
            requirements=[
                {"id": "D1", "statement": "Audit.", "kind": "functional", "priority": "should", "source": "user"}
            ]
        )
        assert any("source 'inferred'" in p for p in self.problems(claimed))

    def test_without_approved_requirements_the_original_rules_apply(self) -> None:
        cfg = ProjectConfiguration.model_validate(configuration())
        assert plan_problems(ProjectPlan.model_validate(plan()), cfg) == []
        empty = ProjectPlan.model_validate(plan(requirements=[]))
        assert any("At least one requirement" in p for p in plan_problems(empty, cfg))
        flagged = ProjectPlan.model_validate(plan(flagged_requirements=[{"id": "R1", "reason": "x"}]))
        assert any("only used when" in p for p in plan_problems(flagged, cfg))


class TestQuestionSelectionAndBlocking:
    """Regressions from the 2026-10-29 live Groq run: a vague brief that got only a tenancy question, and a
    clear brief that was held back by a blocking deployment question."""

    ready: ClassVar[dict] = {"ready": True, "blockers": []}
    not_ready: ClassVar[dict] = {"ready": False, "blockers": []}
    vague_context = staticmethod(lambda **o: analyst_context(personas=[], tenancy="unknown", scope="", **o))
    guessed = staticmethod(lambda: requirement_op(source="inferred", confidence="low", evidence=[]))

    def tenancy_question(self, **overrides):
        return question(
            prompt="Will separate companies share one deployment?",
            kind="yes-no",
            options=[],
            topic="tenancy",
            **overrides,
        )

    def test_vague_brief_cannot_be_reduced_to_a_tenancy_question(self) -> None:
        only_tenancy = first_turn(
            output(context=self.vague_context(), operations=[self.guessed()], questions=[self.tenancy_question()])
        )
        assert any("topic 'users'" in p for p in only_tenancy.problems)
        assert any("topic 'scope'" in p for p in only_tenancy.problems)

    def test_vague_brief_covering_users_scope_and_tenancy_is_accepted(self) -> None:
        covered = first_turn(
            output(
                context=self.vague_context(),
                operations=[self.guessed()],
                questions=[
                    question(prompt="Who will use the app?", kind="free-text", options=[], topic="users"),
                    question(prompt="What must they be able to do first?", kind="free-text", options=[], topic="scope"),
                    self.tenancy_question(),
                ],
            )
        )
        assert covered.problems == [] and not covered.document.readiness.ready

    def test_unknown_platform_needs_a_platform_question(self) -> None:
        result = first_turn(output(context=analyst_context(platform="unknown")))
        assert any("topic 'platform'" in p for p in result.problems)

    def test_clear_brief_with_no_blocking_gaps_declares_readiness(self) -> None:
        ready = first_turn(output(questions=[question(blocking=False)], readiness=self.ready))
        assert ready.problems == [] and ready.document.readiness.ready
        held_back = first_turn(output(questions=[question(blocking=False)], readiness=self.not_ready))
        assert any("Nothing blocks readiness" in p for p in held_back.problems)

    @pytest.mark.parametrize("topic", ["deployment", "cost", "delivery"])
    def test_optional_decisions_never_block(self, topic) -> None:
        optional = question(prompt=f"A {topic} choice?", kind="yes-no", options=[], topic=topic)
        blocking = first_turn(output(questions=[optional]))
        assert any(f"a {topic} question cannot block readiness" in p for p in blocking.problems)
        asked_optionally = first_turn(output(questions=[dict(optional, blocking=False)], readiness=self.ready))
        assert asked_optionally.problems == [] and asked_optionally.document.readiness.ready

    def test_platform_blocks_only_when_unknown(self) -> None:
        platform_q = question(prompt="Web, mobile, or both?", topic="platform", options=["Web", "Mobile", "Both"])
        known = first_turn(output(questions=[platform_q]))
        assert any("platform is already known" in p for p in known.problems)
        unknown = first_turn(output(context=analyst_context(platform="unknown"), questions=[platform_q]))
        assert unknown.problems == [] and not unknown.document.readiness.ready

    @pytest.mark.parametrize("topic", ["users", "scope", "tenancy", "security", "privacy", "data"])
    def test_genuinely_necessary_unknowns_may_block(self, topic) -> None:
        necessary = question(prompt=f"An essential {topic} question?", kind="yes-no", options=[], topic=topic)
        result = first_turn(output(questions=[necessary], readiness=self.not_ready))
        assert result.problems == [] and not result.document.readiness.ready
        claims_ready = first_turn(output(questions=[necessary], readiness=self.ready))
        assert any("is unanswered" in p for p in claims_ready.problems)


class TestLiveOutputFormatRegressions:
    """Formats Groq produced live on 2026-10-29 that carry no different meaning, and ones that do."""

    def test_performance_is_a_question_topic(self) -> None:
        load = question(
            prompt="How many members at peak?", kind="free-text", options=[], topic="performance", blocking=False
        )
        assert first_turn(output(questions=[question(), load])).problems == []

    def test_yes_no_with_exactly_yes_and_no_options_is_normalised(self) -> None:
        restated = first_turn(
            output(questions=[question(), question(prompt="Payments?", kind="yes-no", options=["Yes", "No"])])
        )
        assert restated.problems == [] and restated.questions[-1].options == ()
        other = first_turn(output(questions=[question(prompt="Payments?", kind="yes-no", options=["Yes", "Maybe"])]))
        assert any("take no options" in p for p in other.problems)

    def test_placeholder_evidence_is_dropped_but_real_citations_are_still_checked(self) -> None:
        placeholder = requirement_op(source="inferred", confidence="medium", evidence=["inferred"])
        result = first_turn(output(operations=[requirement_op(), placeholder]))
        assert result.problems == [] and result.document.requirements[1].evidence == []
        invented = requirement_op(source="inferred", confidence="medium", evidence=["inferred", "answer:DQ-009"])
        assert any("no answer to DQ-009" in p for p in first_turn(output(operations=[invented])).problems)
