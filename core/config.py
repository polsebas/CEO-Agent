from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LlmProvider = Literal["auto", "anthropic", "openai", "google"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql://ceo:ceo@localhost:5432/ceo_agent"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    google_gemini_model: str = "gemini-3.5-flash"
    llm_provider: LlmProvider = "auto"
    github_mcp_url: str = "http://localhost:8001"
    github_repo: str = "owner/repo"
    use_in_memory_store: bool = False

    db_pool_min: int = 5
    db_pool_max: int = 20
    mcp_timeout_seconds: float = 3.0
    degraded_success_threshold: float = 0.7
    runtime_health_enforcement: bool = True

    # RRM-3 adaptive thresholds
    adaptive_retry_density_high: float = 0.6
    adaptive_context_pressure_high: float = 0.85
    adaptive_replay_confidence_low: float = 0.5
    adaptive_drift_severity_high: float = 0.5
    adaptive_latency_pressure_high: float = 0.7
    adaptive_session_age_long_seconds: int = 3600
    adaptive_tool_enter_degraded: float = 0.70
    adaptive_tool_exit_degraded: float = 0.82
    adaptive_approval_bias_max: float = 2.0
    adaptive_context_budget_min: float = 0.25
    adaptive_context_budget_relaxed_max: float = 1.0

    otel_service_name: str = "ceo-agent"
    otel_exporter_otlp_endpoint: str = ""
    otel_sdk_disabled: bool = False
    telemetry_enabled: bool = True

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    auth_disabled: bool = False
    allowed_mcp_hosts: str = "localhost,127.0.0.1,github-mcp.internal"

    @property
    def allowed_mcp_hosts_list(self) -> set[str]:
        return {h.strip() for h in self.allowed_mcp_hosts.split(",") if h.strip()}


settings = Settings()
