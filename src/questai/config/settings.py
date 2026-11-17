from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: str = "openai"
    llm_model: str
    llm_temperature: float = 0.2
    llm_base_url: str | None = None

    mcp_server_url: str
    questai_integration_token: SecretStr = Field(min_length=32)

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_base_url: str | None = None

    openai_api_key: str | None = None

    @property
    def llm_models_url(self) -> str:
        base = self.llm_base_url or "https://api.openai.com/v1"
        return f"{base.rstrip('/')}/models"

    @model_validator(mode="after")
    def _resolve_api_base_url(self) -> "Settings":
        if self.api_base_url is None:
            self.api_base_url = f"http://{self.api_host}:{self.api_port}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
