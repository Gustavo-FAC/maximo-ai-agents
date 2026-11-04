"""Configurações da aplicação, lidas de variáveis de ambiente ou do arquivo .env."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr = SecretStr("")
    tenant_id: str = "itambe"

    # LLM (gateway em maximo_agents.llm): provedor e modelo vêm só da configuração.
    llm_provider: str = ""
    llm_model: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 120.0
    maximo_mcp_url: str = ""
    maximo_api_key: SecretStr = SecretStr("")


def get_settings() -> Settings:
    return Settings()
