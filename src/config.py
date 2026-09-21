"""
Application configuration for Instagram Marketing Manager.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM Gateway Configuration
    # Supports local Ollama (http://localhost:11434/v1) or remote gateways
    llm_api_base: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "llama3.2:latest"

    # Target Creator
    creator_handle: str = ""
    creator_url: str = ""

    # Browser & Automation
    headless: bool = False
    session_file: str = "instagram_session.json"
    login_delay_seconds: int = 5
    browser_timeout_ms: int = 45000

    # Project directories
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"

    # Server settings
    server_port: int = 8088
    server_host: str = "127.0.0.1"

    # Outreach settings
    outreach_mode: str = "preview"  # preview or mock


settings = Settings()
# Ensure data directory exists
settings.data_dir.mkdir(parents=True, exist_ok=True)
