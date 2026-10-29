"""Project model and rules. Mirrors `src/domain/projects/{project,catalog,rules,stack-validation}.ts`.

Messages are kept identical to the frontend so both layers report the same problems. Parity is
checked in `tests/test_domain_projects.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

PlatformTarget = Literal["website", "mobile", "both"]
TechnologyId = Literal["react", "nextjs", "flutter", "react-native", "fastapi", "nodejs", "postgresql"]
RequirementId = Literal["authentication", "database", "admin-dashboard", "payments", "notifications", "automated-tests"]
ProjectStatus = Literal[
    "draft", "configured", "queued", "planning", "generating", "testing", "repairing", "ready", "failed"
]

NAME_MAX = 80
DESCRIPTION_MIN = 10
DESCRIPTION_MAX = 2000
CUSTOM_REQUIREMENTS_MAX = 1000
NOTE_MAX = 1000
REFERENCE_URL_MAX = 2048


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecommendStack(_Strict):
    mode: Literal["recommend"]


class CustomStack(_Strict):
    mode: Literal["custom"]
    technologies: list[TechnologyId] = Field(max_length=7)


StackPreference = Annotated[RecommendStack | CustomStack, Field(discriminator="mode")]


class ProjectRequirements(_Strict):
    features: list[RequirementId] = Field(max_length=6)
    # Generous transport bound; the business limit (applied after trimming) is CUSTOM_REQUIREMENTS_MAX.
    custom: str = Field(max_length=CUSTOM_REQUIREMENTS_MAX * 2)


class ProjectConfiguration(_Strict):
    name: str = Field(max_length=NAME_MAX * 2)
    description: str = Field(max_length=DESCRIPTION_MAX * 2)
    platform: PlatformTarget
    referenceUrl: str = Field(max_length=REFERENCE_URL_MAX)
    stack: StackPreference
    requirements: ProjectRequirements


@dataclass(frozen=True)
class Technology:
    id: TechnologyId
    name: str
    category: Literal["web-frontend", "mobile", "backend", "database"]
    platforms: tuple[Literal["website", "mobile"], ...]


TECHNOLOGIES: dict[str, Technology] = {
    t.id: t
    for t in (
        Technology("react", "React", "web-frontend", ("website",)),
        Technology("nextjs", "Next.js", "web-frontend", ("website",)),
        Technology("flutter", "Flutter", "mobile", ("mobile", "website")),
        Technology("react-native", "React Native", "mobile", ("mobile",)),
        Technology("fastapi", "Python / FastAPI", "backend", ("website", "mobile")),
        Technology("nodejs", "Node.js", "backend", ("website", "mobile")),
        Technology("postgresql", "PostgreSQL", "database", ("website", "mobile")),
    )
}


@dataclass
class StackValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _covers(ids: list[str], platform: str) -> bool:
    return any(
        TECHNOLOGIES[i].category in ("web-frontend", "mobile") and platform in TECHNOLOGIES[i].platforms for i in ids
    )


def validate_technologies(platform: PlatformTarget, ids: list[str]) -> StackValidation:
    """Compatibility rules for a concrete technology list (custom stacks and recommended stacks)."""
    result = StackValidation()
    if not ids:
        result.errors.append("Select at least one technology, or let Omniora recommend a stack.")
        return result
    has = set(ids).__contains__
    if has("react") and has("nextjs"):
        result.errors.append("React and Next.js overlap (Next.js already includes React). Choose one web framework.")
    if has("flutter") and has("react-native"):
        result.errors.append("Flutter and React Native are competing mobile frameworks. Choose one.")
    if has("fastapi") and has("nodejs"):
        result.errors.append("Choose a single backend runtime: Python/FastAPI or Node.js.")
    needs_web = platform in ("website", "both")
    needs_mobile = platform in ("mobile", "both")
    if needs_web and not _covers(ids, "website"):
        result.errors.append("A website needs a web client. Add React, Next.js, or Flutter (web).")
    if needs_mobile and not _covers(ids, "mobile"):
        result.errors.append("A mobile app needs a mobile framework. Add Flutter or React Native.")
    if platform == "mobile" and (has("react") or has("nextjs")):
        result.warnings.append("React and Next.js produce websites, so they will not be used in a mobile-only project.")
    if has("postgresql") and not (has("fastapi") or has("nodejs") or has("nextjs")):
        result.errors.append("PostgreSQL needs a server layer. Add FastAPI, Node.js, or Next.js.")
    if has("flutter") and platform == "website":
        result.warnings.append(
            "Flutter web suits app-like experiences; content and SEO-heavy sites are better served by Next.js."
        )
    return result


def validate_stack(platform: PlatformTarget, stack: RecommendStack | CustomStack) -> StackValidation:
    if isinstance(stack, RecommendStack):
        return StackValidation()
    return validate_technologies(platform, list(stack.technologies))


def is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def validate_project_name(name: str) -> str | None:
    trimmed = name.strip()
    if not trimmed:
        return "Give your project a name."
    if len(trimmed) > NAME_MAX:
        return f"Use {NAME_MAX} characters or fewer."
    return None


def validate_description(description: str) -> str | None:
    trimmed = description.strip()
    if not trimmed:
        return "Describe what you want to build."
    if len(trimmed) < DESCRIPTION_MIN:
        return f"Add a little more detail (at least {DESCRIPTION_MIN} characters)."
    if len(trimmed) > DESCRIPTION_MAX:
        return f"Use {DESCRIPTION_MAX} characters or fewer."
    return None


def validate_reference_url(url: str) -> str | None:
    trimmed = url.strip()
    if trimmed and not is_http_url(trimmed):
        return "Enter a full URL starting with http:// or https://."
    return None


def validate_custom_requirements(custom: str) -> str | None:
    if len(custom.strip()) > CUSTOM_REQUIREMENTS_MAX:
        return f"Use {CUSTOM_REQUIREMENTS_MAX} characters or fewer."
    return None


def validate_note(content: str) -> str | None:
    trimmed = content.strip()
    if not trimmed:
        return "Write a note before adding it."
    if len(trimmed) > NOTE_MAX:
        return f"Keep notes under {NOTE_MAX} characters."
    return None


def normalize_configuration(configuration: ProjectConfiguration) -> ProjectConfiguration:
    stack: RecommendStack | CustomStack = configuration.stack
    if isinstance(stack, CustomStack):
        stack = CustomStack(mode="custom", technologies=list(dict.fromkeys(stack.technologies)))
    return ProjectConfiguration(
        name=configuration.name.strip(),
        description=configuration.description.strip(),
        platform=configuration.platform,
        referenceUrl=configuration.referenceUrl.strip(),
        stack=stack,
        requirements=ProjectRequirements(
            features=list(dict.fromkeys(configuration.requirements.features)),
            custom=configuration.requirements.custom.strip(),
        ),
    )


def configuration_problems(configuration: ProjectConfiguration) -> list[str]:
    """All blocking problems, in the same order as the frontend's `blockingMessages`."""
    checks = [
        validate_project_name(configuration.name),
        validate_description(configuration.description),
        validate_reference_url(configuration.referenceUrl),
        validate_custom_requirements(configuration.requirements.custom),
    ]
    return [message for message in checks if message] + validate_stack(
        configuration.platform, configuration.stack
    ).errors
