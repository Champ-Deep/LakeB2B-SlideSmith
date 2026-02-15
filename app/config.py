"""
Application configuration loaded from environment variables.
"""
import os
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """All application settings, loaded from .env file or environment."""

    # --- API Keys ---
    gamma_api_key: str = Field(default="", description="Gamma API key for deck generation")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key for AI models")

    # --- Gamma Config ---
    gamma_theme_id: str = Field(default="", description="Pre-created theme ID in Gamma")
    gamma_api_base_url: str = Field(default="https://public-api.gamma.app/v1.0", description="Gamma API v1.0 base URL")

    # --- Database ---
    database_url: str = Field(default="", description="PostgreSQL connection URL")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- Model Configuration ---
    pitch_generation_model: str = Field(default="anthropic/claude-3.5-sonnet", description="Model for pitch generation")
    service_mapping_model: str = Field(default="anthropic/claude-3.5-haiku", description="Model for service mapping")
    pitch_max_tokens: int = Field(default=4096, description="Max tokens for pitch generation")
    service_mapping_max_tokens: int = Field(default=512, description="Max tokens for service mapping")
    research_model: str = Field(default="perplexity/sonar", description="Model for company research")

    # --- App ---
    upload_dir: str = Field(default="./uploads")
    output_dir: str = Field(default="./output")
    max_rows_per_upload: int = Field(default=100)

    # --- Paths ---
    services_catalog_path: str = Field(default="./data/services_catalog.yaml")
    research_system_prompt_path: str = Field(default="./data/research_system_prompt.txt")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def async_database_url(self) -> str:
        """Convert Railway's DATABASE_URL to asyncpg format for SQLAlchemy."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


# Singleton settings instance
settings = Settings()


def ensure_dirs():
    """Create upload and output directories if they don't exist."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
