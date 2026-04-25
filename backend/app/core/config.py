"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Java Patching Application"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/javapatching"
    redis_url: str = "redis://localhost:6379"

    # Authentication
    secret_key: str = "change-this-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LLM Providers (all optional, at least one required for suggestions)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4-turbo"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    google_api_key: str | None = None
    google_model: str = "gemini-1.5-pro"

    # Self-hosted LLM (Ollama or OpenAI-compatible API)
    ollama_base_url: str | None = None  # e.g., http://localhost:11434
    ollama_model: str = "llama3"

    # Default LLM provider (gemini recommended for cost-efficiency)
    default_llm_provider: str = "gemini"

    # SSO Configuration
    sso_google_client_id: str | None = None
    sso_google_client_secret: str | None = None
    sso_github_client_id: str | None = None
    sso_github_client_secret: str | None = None
    sso_microsoft_client_id: str | None = None
    sso_microsoft_client_secret: str | None = None
    sso_microsoft_tenant_id: str = "common"  # Use 'common' for multi-tenant

    # Repository storage
    repos_base_path: str = "/app/repos"

    # JDK Release Notes Sources
    openjdk_release_notes_url: str = "https://openjdk.org/projects/jdk-updates/"
    adoptium_api_url: str = "https://api.adoptium.net/v3"

    @property
    def available_llm_providers(self) -> list[str]:
        """Return list of configured LLM providers."""
        providers = []
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        if self.google_api_key:
            providers.append("gemini")
        if self.ollama_base_url:
            providers.append("ollama")
        return providers


settings = Settings()
