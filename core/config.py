from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql://ceo:ceo@localhost:5432/ceo_agent"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    github_mcp_url: str = "http://localhost:8001"
    github_repo: str = "owner/repo"
    use_in_memory_store: bool = False

    db_pool_min: int = 5
    db_pool_max: int = 20
    mcp_timeout_seconds: float = 3.0
    degraded_success_threshold: float = 0.7

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    auth_disabled: bool = False
    allowed_mcp_hosts: str = "localhost,127.0.0.1,github-mcp.internal"

    @property
    def allowed_mcp_hosts_list(self) -> set[str]:
        return {h.strip() for h in self.allowed_mcp_hosts.split(",") if h.strip()}


settings = Settings()
