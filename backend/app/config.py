"""Environment-driven configuration.

Rules:
- development: missing keys are logged as warnings, app still boots (so /health works).
- production: required keys are validated at startup and the app crashes loudly.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("mirage.config")

# Keys that must be present when ENVIRONMENT=production
_PRODUCTION_REQUIRED = [
    "GROQ_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "NEO4J_URI",
    "NEO4J_PASSWORD",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- LLM providers ----
    llm_provider: str = "auto"  # auto | groq | gemini | ollama
    groq_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # ---- Databases ----
    supabase_url: str = ""
    supabase_anon_key: str = ""
    neo4j_uri: str = ""
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""

    # ---- Runtime ----
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # ---- Service metadata ----
    service_name: str = "mirage-api"
    version: str = "0.1.0"

    @field_validator("environment")
    @classmethod
    def _normalize_env(cls, v: str) -> str:
        return v.strip().lower()

    # ---- Derived helpers -------------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def available_llm_providers(self) -> list[str]:
        """Providers usable right now, in auto-selection order."""
        providers: list[str] = []
        if self.llm_provider != "auto":
            if self.llm_provider == "groq" and self.groq_api_key:
                providers.append("groq")
            elif self.llm_provider == "gemini" and self.gemini_api_key:
                providers.append("gemini")
            elif self.llm_provider == "ollama":
                providers.append("ollama")
            return providers
        if self.groq_api_key:
            providers.append("groq")
        if self.gemini_api_key:
            providers.append("gemini")
        providers.append("ollama")  # local, needs no key
        return providers

    @property
    def primary_llm_provider(self) -> str | None:
        providers = self.available_llm_providers
        return providers[0] if providers else None

    def missing_production_keys(self) -> list[str]:
        return [k for k in _PRODUCTION_REQUIRED if not getattr(self, k.lower(), "")]

    def validate_startup(self) -> None:
        """Crash loudly in production; warn in development."""
        missing = self.missing_production_keys()
        if self.is_production and missing:
            raise RuntimeError(
                f"Missing required env vars for production: {', '.join(missing)}"
            )
        if missing:
            logger.warning(
                "Missing optional env vars (fine in development): %s",
                ", ".join(missing),
            )
        logger.info(
            "LLM providers available: %s (provider=%s)",
            ", ".join(self.available_llm_providers) or "none",
            self.llm_provider,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
