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
    gamma_api_base_url: str = Field(default="https://api.gamma.app/api", description="Gamma API base URL")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- App ---
    upload_dir: str = Field(default="./uploads")
    output_dir: str = Field(default="./output")
    max_rows_per_upload: int = Field(default=100)

    # --- Paths ---
    services_catalog_path: str = Field(default="./data/services_catalog.yaml")
    research_system_prompt_path: str = Field(default="./data/research_system_prompt.txt")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton settings instance
settings = Settings()


def ensure_dirs():
    """Create upload and output directories if they don't exist."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.output_dir, exist_ok=True)
