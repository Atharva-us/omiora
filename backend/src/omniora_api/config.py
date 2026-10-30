"""Validated, environment-based configuration. The only module that reads the environment."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]
ModelProviderName = Literal["anthropic", "groq"]


@dataclass(frozen=True)
class PlanningDefaults:
    model: str
    effort: Effort
    max_output_tokens: int
    # Requirements Analyst turns: output budget, and the most a single request (estimated prompt
    # plus requested completion) may use. Turns whose prompt would exceed it fail honestly.
    analyst_max_output_tokens: int
    request_token_budget: int


PROVIDER_DEFAULTS: dict[str, PlanningDefaults] = {
    "anthropic": PlanningDefaults(
        model="claude-opus-5-5",
        effort="high",
        max_output_tokens=16000,
        analyst_max_output_tokens=8000,
        request_token_budget=150_000,
    ),
    # Groq Developer-tier gpt-oss-120b allows 8K tokens per minute including the requested
    # completion budget, so the defaults leave room for the prompt and schema. Hidden reasoning
    # counts toward the completion budget: 3,000 analyst tokens truncated live outputs.
    "groq": PlanningDefaults(
        model="openai/gpt-oss-120b",
        effort="medium",
        max_output_tokens=6000,
        analyst_max_output_tokens=5000,
        request_token_budget=7600,
    ),
}


class Settings(BaseSettings):
    """Every variable is prefixed `OMNIORA_` except provider credentials, which use each
    provider's conventional name (`ANTHROPIC_API_KEY`, `GROQ_API_KEY`). Secrets are `SecretStr`
    so they never appear in reprs or logs."""

    model_config = SettingsConfigDict(env_prefix="OMNIORA_", env_file=".env", extra="ignore")

    env: Literal["development", "test", "production"] = "development"
    database_url: str
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # HTTP and browser security
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173"])
    cookie_secure: bool | None = None  # defaults to True in production
    session_ttl_hours: int = Field(default=24 * 14, ge=1, le=24 * 90)
    max_body_bytes: int = Field(default=64 * 1024, ge=1024, le=1024 * 1024)

    # Abuse limits
    runs_per_user_per_hour: int = Field(default=10, ge=1)
    signin_attempts_per_window: int = Field(default=10, ge=1)
    signin_window_seconds: int = Field(default=15 * 60, ge=1)

    # Model provider (credentials stay server-side). The provider is chosen explicitly; a
    # credential for another provider being present never switches it.
    model_provider: ModelProviderName = "anthropic"
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_refusal_fallback: bool = True
    groq_api_key: SecretStr | None = Field(default=None, validation_alias="GROQ_API_KEY")
    # Unset planning settings take the selected provider's defaults (PROVIDER_DEFAULTS).
    pm_model: str | None = None
    pm_effort: Effort | None = None
    pm_max_output_tokens: int | None = Field(default=None, ge=1024, le=64000)
    pm_max_attempts: int = Field(default=3, ge=1, le=5)
    pm_request_token_budget: int | None = Field(default=None, ge=2048)
    # Requirements Analyst (Agent 2). It uses the same provider and model as planning.
    analyst_max_output_tokens: int | None = Field(default=None, ge=1024, le=64000)
    analyst_request_token_budget: int | None = Field(default=None, ge=2048)
    analyst_max_attempts: int = Field(default=3, ge=1, le=5)
    analyst_max_turns: int = Field(default=8, ge=1, le=20)
    analyst_turns_per_user_per_hour: int = Field(default=30, ge=1)
    model_timeout_seconds: float = Field(default=300.0, gt=0, le=1800)
    model_transport_retries: int = Field(default=2, ge=0, le=5)

    # Worker
    worker_lease_seconds: int = Field(default=60, ge=10)
    worker_poll_seconds: float = Field(default=1.0, gt=0)
    job_max_deliveries: int = Field(default=3, ge=1, le=10)

    # Server-sent events
    sse_poll_seconds: float = Field(default=1.0, gt=0)
    sse_heartbeat_seconds: float = Field(default=15.0, gt=0)
    sse_max_stream_seconds: float = Field(default=300.0, gt=0)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3(cls, value: str) -> str:
        if value.startswith("postgresql://"):
            return "postgresql+psycopg://" + value.removeprefix("postgresql://")
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("OMNIORA_DATABASE_URL must be a PostgreSQL URL (postgresql://...)")
        return value

    @model_validator(mode="after")
    def _production_guards(self) -> Settings:
        if self.cookie_secure is None:
            self.cookie_secure = self.env == "production"
        if self.env == "production":
            problems = []
            if not self.cookie_secure:
                problems.append("OMNIORA_COOKIE_SECURE must be true in production")
            if not self.cors_origins or "*" in self.cors_origins:
                problems.append("OMNIORA_CORS_ORIGINS must list explicit origins in production")
            if any(not origin.startswith("https://") for origin in self.cors_origins):
                problems.append("OMNIORA_CORS_ORIGINS must use https in production")
            if problems:
                raise ValueError("; ".join(problems))
        return self

    @property
    def model_api_key(self) -> str | None:
        """The credential for the selected provider only."""
        secret = self.groq_api_key if self.model_provider == "groq" else self.anthropic_api_key
        value = secret.get_secret_value().strip() if secret is not None else ""
        return value or None

    @property
    def model_configured(self) -> bool:
        return self.model_api_key is not None

    @property
    def planning_model(self) -> str:
        return self.pm_model or PROVIDER_DEFAULTS[self.model_provider].model

    @property
    def planning_effort(self) -> Effort:
        return self.pm_effort or PROVIDER_DEFAULTS[self.model_provider].effort

    @property
    def planning_max_output_tokens(self) -> int:
        return self.pm_max_output_tokens or PROVIDER_DEFAULTS[self.model_provider].max_output_tokens

    @property
    def planning_request_token_budget(self) -> int:
        return self.pm_request_token_budget or PROVIDER_DEFAULTS[self.model_provider].request_token_budget

    @property
    def analyst_output_tokens(self) -> int:
        return self.analyst_max_output_tokens or PROVIDER_DEFAULTS[self.model_provider].analyst_max_output_tokens

    @property
    def analyst_token_budget(self) -> int:
        return self.analyst_request_token_budget or PROVIDER_DEFAULTS[self.model_provider].request_token_budget


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
