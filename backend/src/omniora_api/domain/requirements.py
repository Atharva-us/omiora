"""Agent 2 (Requirements Analyst) contract: the versioned requirements document, the analyst's
per-turn output, and the deterministic rules both must satisfy. Mirrored by
`src/domain/requirements/requirements.ts`.

Authority rules, enforced here rather than trusted to the prompt:
- The server assigns requirement ids (`REQ-001`, ...). The model proposes operations only: `add`
  (no id), `update` and `deprecate` (naming an existing id). Ids are never reused and nothing is
  ever removed: a deprecated requirement stays in every later version.
- Anything attributed to the user cites evidence that exists: an answered question, a brief
  field, or a note. An "I don't know" answer is never evidence for a fact.
- Readiness is recomputed: a `ready` claim is rejected unless every rule holds.
- A multi-tenant product must carry an active "must" requirement tagged `tenant-isolation`.
- Discovery covers the fundamentals: while the users or the core features are unknown, a question
  about them must be open or answered, so no single topic (such as tenancy) crowds them out.
- A question may block readiness only when its answer is needed for a safe, useful baseline.
  Deployment, cost, and delivery choices never block, and neither does a platform question when the
  platform is known. A "not ready" claim must be explained by something that actually blocks.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 1
MAX_QUESTIONS_PER_TURN = 5
REQUIREMENT_ID = re.compile(r"^REQ-\d{3,}$")
QUESTION_KEY = re.compile(r"^DQ-\d{3,}$")
BRIEF_FIELDS = ("name", "description", "platform", "stack", "features", "custom", "referenceUrl")

RequirementKind = Literal["functional", "non-functional", "constraint"]
Priority = Literal["must", "should", "could", "wont"]
Confidence = Literal["high", "medium", "low"]
Source = Literal["brief", "note", "answer", "inferred"]
Tag = Literal[
    "security",
    "privacy",
    "tenant-isolation",
    "accessibility",
    "performance",
    "reliability",
    "compliance",
    "billing",
    "data",
    "integration",
]
TAGS: tuple[str, ...] = Tag.__args__  # type: ignore[attr-defined]
Tenancy = Literal["single", "multi", "unknown"]
ContextPlatform = Literal["website", "mobile", "both", "unknown"]
QuestionKind = Literal["single-choice", "multiple-choice", "free-text", "yes-no"]
QuestionTopic = Literal[
    "scope",
    "users",
    "tenancy",
    "security",
    "privacy",
    "data",
    "integrations",
    "platform",
    "performance",
    "deployment",
    "cost",
    "delivery",
    "other",
]
QUESTION_TOPICS: tuple[str, ...] = QuestionTopic.__args__  # type: ignore[attr-defined]
# Decisions that can be assumed or settled later without making the requirements unsafe or unusable.
NON_BLOCKING_TOPICS = frozenset({"deployment", "cost", "delivery"})
QuestionStatus = Literal["open", "answered", "withdrawn"]


def _enum_values(literal: object) -> list[str]:
    return list(literal.__args__)  # type: ignore[attr-defined]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Persona(_Strict):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(max_length=300)


class ProjectContext(_Strict):
    goal: str = Field(min_length=1, max_length=1000)
    scope: str = Field(max_length=1000)
    platform: ContextPlatform
    deployment: str = Field(max_length=500)
    personas: list[Persona] = Field(max_length=10)
    tenancy: Tenancy
    constraints: list[str] = Field(max_length=20)
    integrations: list[str] = Field(max_length=20)
    out_of_scope: list[str] = Field(max_length=20)


class Requirement(_Strict):
    id: str = Field(pattern=REQUIREMENT_ID.pattern)
    statement: str = Field(min_length=1, max_length=500)
    kind: RequirementKind
    priority: Priority
    confidence: Confidence
    source: Source
    evidence: list[str] = Field(max_length=10)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=8)
    tags: list[Tag] = Field(max_length=6)
    status: Literal["active", "deprecated"]
    deprecation_reason: str = Field(default="", max_length=300)


class Assumption(_Strict):
    statement: str = Field(min_length=1, max_length=500)
    confidence: Confidence
    basis: list[str] = Field(max_length=5)  # question keys the assumption stands in for


class OpenQuestionRef(_Strict):
    key: str
    prompt: str
    blocking: bool
    topic: QuestionTopic
    status: Literal["open", "unknown"]  # unknown: answered "I don't know"


class Readiness(_Strict):
    ready: bool
    blockers: list[str] = Field(max_length=20)


class RequirementsDocument(_Strict):
    """One immutable version. `open_questions` is a server-written snapshot, never model output."""

    schema_version: Literal[1] = SCHEMA_VERSION
    context: ProjectContext
    requirements: list[Requirement] = Field(max_length=100)
    assumptions: list[Assumption] = Field(max_length=30)
    open_questions: list[OpenQuestionRef] = Field(max_length=60)
    readiness: Readiness
    decisions: list[str] = Field(max_length=10)

    def active(self) -> list[Requirement]:
        return [r for r in self.requirements if r.status == "active"]


def content_sha256(document: RequirementsDocument) -> str:
    canonical = json.dumps(document.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


# --- analyst output (untrusted) -----------------------------------------------------------


class RequirementOperation(_Strict):
    op: Literal["add", "update", "deprecate"]
    id: str = Field(max_length=16)  # "" for add: the server assigns ids
    statement: str = Field(max_length=500)
    kind: RequirementKind
    priority: Priority
    confidence: Confidence
    source: Source
    evidence: list[str] = Field(max_length=10)
    acceptance_criteria: list[str] = Field(max_length=8)
    tags: list[Tag] = Field(max_length=6)
    reason: str = Field(max_length=300)  # required to deprecate, or to lower a "must"

    @model_validator(mode="after")
    def _drop_placeholder_evidence(self) -> RequirementOperation:
        # Seen live: inferred requirements citing the literal word "inferred". It is a placeholder, not a
        # citation; the requirement stays marked inferred. Real citations are checked in full elsewhere.
        if self.source == "inferred":
            self.evidence = [ref for ref in self.evidence if ref.strip().lower() != "inferred"]
        return self


class ProposedQuestion(_Strict):
    prompt: str = Field(min_length=1, max_length=300)
    why: str = Field(min_length=1, max_length=300)
    kind: QuestionKind
    options: list[str] = Field(max_length=8)
    blocking: bool
    topic: QuestionTopic
    relates_to: list[str] = Field(max_length=5)

    @model_validator(mode="after")
    def _yes_no_takes_no_options(self) -> ProposedQuestion:
        # Seen live: yes-no questions listing exactly ["Yes", "No"]. That restates the kind, so it is dropped;
        # any other options on a yes-no question are still rejected.
        if self.kind == "yes-no" and sorted(o.strip().lower() for o in self.options) == ["no", "yes"]:
            self.options = []
        return self


class AnalystTurnOutput(_Strict):
    context: ProjectContext
    operations: list[RequirementOperation] = Field(max_length=40)
    questions: list[ProposedQuestion] = Field(max_length=MAX_QUESTIONS_PER_TURN)
    withdraw_questions: list[str] = Field(max_length=20)
    assumptions: list[Assumption] = Field(max_length=30)
    readiness: Readiness
    decisions: list[str] = Field(max_length=10)


def _string_array(enum: list[str] | None = None) -> dict[str, object]:
    items: dict[str, object] = {"type": "string"}
    if enum:
        items["enum"] = enum
    return {"type": "array", "items": items}


def _object(properties: dict[str, object]) -> dict[str, object]:
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def _enum(literal: object) -> dict[str, object]:
    return {"type": "string", "enum": _enum_values(literal)}


def analyst_output_schema() -> dict[str, object]:
    """Structured-output schema, limited to widely supported keywords (as `plan_output_schema`).
    Lengths and counts are enforced afterwards by `AnalystTurnOutput`."""
    assumption = _object({"statement": {"type": "string"}, "confidence": _enum(Confidence), "basis": _string_array()})
    return _object(
        {
            "context": _object(
                {
                    "goal": {"type": "string"},
                    "scope": {"type": "string"},
                    "platform": _enum(ContextPlatform),
                    "deployment": {"type": "string"},
                    "personas": {
                        "type": "array",
                        "items": _object({"name": {"type": "string"}, "description": {"type": "string"}}),
                    },
                    "tenancy": _enum(Tenancy),
                    "constraints": _string_array(),
                    "integrations": _string_array(),
                    "out_of_scope": _string_array(),
                }
            ),
            "operations": {
                "type": "array",
                "items": _object(
                    {
                        "op": {"type": "string", "enum": ["add", "update", "deprecate"]},
                        "id": {"type": "string"},
                        "statement": {"type": "string"},
                        "kind": _enum(RequirementKind),
                        "priority": _enum(Priority),
                        "confidence": _enum(Confidence),
                        "source": _enum(Source),
                        "evidence": _string_array(),
                        "acceptance_criteria": _string_array(),
                        "tags": _string_array(_enum_values(Tag)),
                        "reason": {"type": "string"},
                    }
                ),
            },
            "questions": {
                "type": "array",
                "items": _object(
                    {
                        "prompt": {"type": "string"},
                        "why": {"type": "string"},
                        "kind": _enum(QuestionKind),
                        "options": _string_array(),
                        "blocking": {"type": "boolean"},
                        "topic": _enum(QuestionTopic),
                        "relates_to": _string_array(),
                    }
                ),
            },
            "withdraw_questions": _string_array(),
            "assumptions": {"type": "array", "items": assumption},
            "readiness": _object({"ready": {"type": "boolean"}, "blockers": _string_array()}),
            "decisions": _string_array(),
        }
    )


# --- validation state ---------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionState:
    """A persisted question with its latest answer, as the API recorded it."""

    key: str
    prompt: str
    kind: QuestionKind
    options: tuple[str, ...]
    blocking: bool
    topic: QuestionTopic
    status: QuestionStatus
    unknown: bool = False  # answered "I don't know"

    @property
    def has_factual_answer(self) -> bool:
        return self.status == "answered" and not self.unknown


@dataclass(frozen=True)
class TurnContext:
    previous: RequirementsDocument | None  # latest version in the session, or the approved base
    questions: tuple[QuestionState, ...]
    note_count: int
    final_turn: bool = False


def _normalise(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def _number(requirement_id: str) -> int:
    return int(requirement_id.split("-", 1)[1])


def next_requirement_number(previous: RequirementsDocument | None) -> int:
    return max((_number(r.id) for r in previous.requirements), default=0) + 1 if previous else 1


def _evidence_problems(where: str, source: str, evidence: list[str], questions: dict[str, QuestionState], notes: int):
    problems: list[str] = []
    cites = {"answer": False, "brief": False, "note": False}
    for ref in evidence:
        kind, _, target = ref.partition(":")
        if kind == "answer":
            question = questions.get(target)
            if question is None or question.status != "answered":
                problems.append(f"{where} cites {ref!r}, but no answer to {target} has been submitted.")
            elif question.unknown:
                if source == "answer":
                    problems.append(f'{where} cites {ref!r} as a fact, but the user answered "I don\'t know".')
            else:
                cites["answer"] = True
        elif kind == "brief":
            if target not in BRIEF_FIELDS:
                problems.append(f"{where} cites unknown brief field {ref!r}.")
            else:
                cites["brief"] = True
        elif kind == "note":
            if not target.isdigit() or not 1 <= int(target) <= notes:
                problems.append(f"{where} cites {ref!r}, but the project has {notes} note(s).")
            else:
                cites["note"] = True
        else:
            problems.append(f"{where} has malformed evidence {ref!r} (use answer:DQ-001, brief:<field>, or note:<n>).")
    if source in cites and not cites[source]:
        problems.append(
            f"{where} has source {source!r} but no valid {source} evidence; do not attribute it to the user."
        )
    return problems


def _operation_problems(output: AnalystTurnOutput, context: TurnContext, questions: dict[str, QuestionState]):
    problems: list[str] = []
    existing = {r.id: r for r in context.previous.requirements} if context.previous else {}
    seen: set[str] = set()
    for index, op in enumerate(output.operations):
        where = f"operations[{index}] ({op.op} {op.id or 'new'})"
        if op.op == "add":
            if op.id:
                problems.append(f"{where}: leave id empty for additions; the server assigns requirement ids.")
        else:
            if op.id in seen:
                problems.append(f"{where}: requirement {op.id!r} appears in more than one operation.")
            seen.add(op.id)
            current = existing.get(op.id)
            if current is None:
                problems.append(f"{where}: unknown requirement id {op.id!r}.")
                continue
            if current.status == "deprecated":
                problems.append(f"{where}: {op.id} is deprecated and cannot change; add a new requirement instead.")
                continue
            weakens = current.priority == "must" and (op.op == "deprecate" or op.priority != "must")
            if weakens:
                user_backed = any(
                    ref.startswith("answer:")
                    and questions.get(ref[7:]) is not None
                    and questions[ref[7:]].has_factual_answer
                    for ref in op.evidence
                )
                if not op.reason.strip() or not user_backed:
                    problems.append(
                        f"{where}: {op.id} is a must-have; removing or lowering it needs a reason and evidence "
                        "from the user's answer (answer:DQ-...)."
                    )
            if op.op == "deprecate":
                if not op.reason.strip():
                    problems.append(f"{where}: give a reason for deprecating {op.id}.")
                continue
        if not op.statement.strip():
            problems.append(f"{where}: statement is required.")
        if not op.acceptance_criteria or not all(c.strip() for c in op.acceptance_criteria):
            problems.append(f"{where}: at least one measurable acceptance criterion is required.")
        if op.source == "inferred" and op.confidence == "high":
            problems.append(f"{where}: an inferred requirement cannot have high confidence.")
        problems += _evidence_problems(where, op.source, op.evidence, questions, context.note_count)
    return problems


def _question_problems(output: AnalystTurnOutput, context: TurnContext, questions: dict[str, QuestionState]):
    problems: list[str] = []
    known_prompts = {_normalise(q.prompt): q.key for q in context.questions if q.status != "withdrawn"}
    requirement_ids = {r.id for r in context.previous.requirements} if context.previous else set()
    if context.final_turn and output.questions:
        problems.append("This is the final discovery turn: ask no new questions; record remaining gaps as assumptions.")
    new_prompts: set[str] = set()
    for index, question in enumerate(output.questions):
        where = f"questions[{index}]"
        prompt = _normalise(question.prompt)
        if prompt in known_prompts:
            problems.append(f"{where} repeats {known_prompts[prompt]}; do not ask a question twice.")
        if prompt in new_prompts:
            problems.append(f"{where} is a duplicate of another question in this turn.")
        new_prompts.add(prompt)
        options = [o.strip() for o in question.options]
        if question.kind in ("single-choice", "multiple-choice"):
            if len(options) < 2 or not all(options) or len(set(options)) != len(options):
                problems.append(f"{where}: choice questions need at least two distinct, non-empty options.")
        elif options:
            problems.append(f"{where}: {question.kind} questions take no options.")
        for ref in question.relates_to:
            if ref not in requirement_ids:
                problems.append(f"{where}: relates_to names unknown requirement {ref!r}.")
        if question.blocking and question.topic in NON_BLOCKING_TOPICS:
            problems.append(
                f"{where}: a {question.topic} question cannot block readiness; ask it as non-blocking or record an "
                "assumption."
            )
        if question.blocking and question.topic == "platform" and output.context.platform != "unknown":
            problems.append(
                f"{where}: the platform is already known ({output.context.platform}), so a platform question cannot "
                "block readiness."
            )
    for key in output.withdraw_questions:
        question = questions.get(key)
        if question is None or question.status != "open":
            problems.append(f"withdraw_questions: {key!r} is not an open question.")
    for index, assumption in enumerate(output.assumptions):
        for key in assumption.basis:
            question = questions.get(key)
            if question is None or question.status == "withdrawn":
                problems.append(f"assumptions[{index}] cites unknown question {key!r}.")
            elif question.unknown and assumption.confidence != "low":
                problems.append(
                    f'assumptions[{index}] stands in for an "I don\'t know" answer ({key}), '
                    "so its confidence must be low."
                )
    return problems


def questions_after_turn(
    context: TurnContext, output: AnalystTurnOutput, first_number: int
) -> tuple[QuestionState, ...]:
    """Persisted questions plus this turn's new ones (keys assigned from `first_number`)."""
    withdrawn = set(output.withdraw_questions)
    current = tuple(
        QuestionState(**{**q.__dict__, "status": "withdrawn"}) if q.key in withdrawn else q for q in context.questions
    )
    added = tuple(
        QuestionState(
            key=f"DQ-{first_number + offset:03d}",
            prompt=q.prompt,
            kind=q.kind,
            options=tuple(q.options),
            blocking=q.blocking,
            topic=q.topic,
            status="open",
        )
        for offset, q in enumerate(output.questions)
    )
    return current + added


def apply_operations(
    previous: RequirementsDocument | None, operations: list[RequirementOperation]
) -> list[Requirement]:
    """Server-side merge: additions get fresh ids, updates keep theirs, deprecations keep the row."""
    requirements = [r.model_copy() for r in previous.requirements] if previous else []
    index = {r.id: position for position, r in enumerate(requirements)}
    number = next_requirement_number(previous)
    for op in operations:
        fields = {
            "statement": op.statement.strip(),
            "kind": op.kind,
            "priority": op.priority,
            "confidence": op.confidence,
            "source": op.source,
            "evidence": op.evidence,
            "acceptance_criteria": [c.strip() for c in op.acceptance_criteria],
            "tags": list(dict.fromkeys(op.tags)),
        }
        if op.op == "add":
            requirements.append(Requirement(id=f"REQ-{number:03d}", status="active", **fields))
            number += 1
        elif op.op == "update":
            requirements[index[op.id]] = Requirement(id=op.id, status="active", **fields)
        else:
            current = requirements[index[op.id]]
            requirements[index[op.id]] = current.model_copy(
                update={"status": "deprecated", "deprecation_reason": op.reason.strip()}
            )
    return requirements


def document_problems(document: RequirementsDocument) -> list[str]:
    """Rules every stored version satisfies, whatever its readiness."""
    problems: list[str] = []
    ids = [r.id for r in document.requirements]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        problems.append(f"Duplicate requirement ids: {', '.join(duplicates)}.")
    if document.context.tenancy == "multi" and not tenant_isolation_requirements(document):
        problems.append(
            "The product is multi-tenant, so an active 'must' requirement tagged 'tenant-isolation' is required, "
            "with acceptance criteria proving that one tenant cannot read or change another tenant's data."
        )
    if document.context.tenancy == "unknown" and not any(
        q.topic == "tenancy" and q.blocking and q.status == "open" for q in document.open_questions
    ):
        problems.append(
            "The tenancy model is unknown: ask a blocking question with topic 'tenancy' (or set tenancy from the "
            "evidence) before continuing."
        )
    return problems


def tenant_isolation_requirements(document: RequirementsDocument) -> list[Requirement]:
    return [
        r
        for r in document.active()
        if "tenant-isolation" in r.tags and r.priority == "must" and any(c.strip() for c in r.acceptance_criteria)
    ]


def readiness_blockers(document: RequirementsDocument, questions: tuple[QuestionState, ...]) -> list[str]:
    """Why a version cannot be declared ready. Empty means it can."""
    blockers: list[str] = []
    covered_unknowns = {key for assumption in document.assumptions for key in assumption.basis}
    for question in questions:
        if not question.blocking or question.status == "withdrawn":
            continue
        if question.status == "open":
            blockers.append(f"Blocking question {question.key} is unanswered.")
        elif question.unknown and question.key not in covered_unknowns:
            blockers.append(
                f'Blocking question {question.key} was answered "I don\'t know" and no assumption records how it '
                "will be handled."
            )
    if document.context.tenancy == "unknown":
        blockers.append("The tenancy model is still unknown.")
    if not any(r.priority == "must" for r in document.active()):
        blockers.append("There is no active must-have requirement.")
    blockers += document_problems(document)
    return blockers


def open_question_snapshot(questions: tuple[QuestionState, ...]) -> list[OpenQuestionRef]:
    return [
        OpenQuestionRef(
            key=q.key, prompt=q.prompt, blocking=q.blocking, topic=q.topic, status="unknown" if q.unknown else "open"
        )
        for q in questions
        if q.status == "open" or (q.status == "answered" and q.unknown)
    ]


def coverage_problems(document: RequirementsDocument, questions: tuple[QuestionState, ...]) -> list[str]:
    """Fundamental unknowns that need a question (open or answered) before discovery can move on."""
    asked = {q.topic for q in questions if q.status != "withdrawn"}
    problems: list[str] = []
    if not document.context.personas and "users" not in asked:
        problems.append("Who the users are is unknown: ask a question with topic 'users'.")
    user_backed_must = any(r.priority == "must" and r.source != "inferred" for r in document.active())
    if not user_backed_must and "scope" not in asked:
        problems.append(
            "No must-have requirement comes from the brief, a note, or an answer yet: ask what the users must be "
            "able to do (topic 'scope')."
        )
    if document.context.platform == "unknown" and "platform" not in asked:
        problems.append("The platform is unknown: ask a question with topic 'platform'.")
    return problems


@dataclass(frozen=True)
class TurnResult:
    document: RequirementsDocument | None
    questions: tuple[QuestionState, ...]
    problems: list[str]


def evaluate_turn(output: AnalystTurnOutput, context: TurnContext, first_question_number: int) -> TurnResult:
    """Validates a shape-valid analyst output against persisted state and builds the next version.

    `first_question_number` is the number the server will give the first new question (DQ-n)."""
    questions = {q.key: q for q in context.questions}
    problems = _operation_problems(output, context, questions) + _question_problems(output, context, questions)
    if problems:
        return TurnResult(None, context.questions, problems)

    after = questions_after_turn(context, output, first_question_number)
    draft = RequirementsDocument(
        context=output.context,
        requirements=apply_operations(context.previous, output.operations),
        assumptions=output.assumptions,
        open_questions=open_question_snapshot(after),
        readiness=Readiness(ready=False, blockers=[]),
        decisions=output.decisions,
    )
    problems = document_problems(draft)
    if not context.final_turn:
        problems += coverage_problems(draft, after)
    blockers = readiness_blockers(draft, after)
    if output.readiness.ready and blockers:
        problems += [f"Discovery is not ready: {blocker}" for blocker in blockers]
    if not output.readiness.ready and not blockers:
        problems.append(
            "Nothing blocks readiness: there is no unanswered blocking question and every rule holds. Declare "
            "ready=true, or mark a question blocking only if its answer is needed for a safe, useful baseline."
        )
    if problems:
        return TurnResult(None, context.questions, problems)

    ready = output.readiness.ready and not blockers
    reported = blockers if not ready else []
    claimed = [b for b in output.readiness.blockers if b.strip()] if not ready else []
    document = draft.model_copy(update={"readiness": Readiness(ready=ready, blockers=(reported + claimed)[:20])})
    return TurnResult(document, after, [])


@dataclass(frozen=True)
class ApprovedRequirements:
    """What Agent 1 receives: one exact, approved, immutable version."""

    version_id: str
    version: int
    content_sha256: str
    document: RequirementsDocument

    def must_ids(self) -> set[str]:
        return {r.id for r in self.document.active() if r.priority == "must"}


DIFF_FIELDS = ("statement", "kind", "priority", "confidence", "source", "evidence", "acceptance_criteria", "tags")


@dataclass(frozen=True)
class RequirementChange:
    id: str
    fields: list[str]


@dataclass(frozen=True)
class DocumentDiff:
    added: list[str]
    deprecated: list[str]
    changed: list[RequirementChange]
    context_fields: list[str]


def diff_documents(old: RequirementsDocument, new: RequirementsDocument) -> DocumentDiff:
    """What changed between two versions, by requirement id. Ids are stable, so this is exact."""
    before = {r.id: r for r in old.requirements}
    added = [r.id for r in new.requirements if r.id not in before]
    deprecated = [
        r.id
        for r in new.requirements
        if r.id in before and before[r.id].status == "active" and r.status == "deprecated"
    ]
    changed = []
    for requirement in new.requirements:
        previous = before.get(requirement.id)
        if previous is None or requirement.id in deprecated:
            continue
        fields = [name for name in DIFF_FIELDS if getattr(previous, name) != getattr(requirement, name)]
        if fields:
            changed.append(RequirementChange(requirement.id, fields))
    context_fields = [
        name for name in ProjectContext.model_fields if getattr(old.context, name) != getattr(new.context, name)
    ]
    return DocumentDiff(added, deprecated, changed, context_fields)
