"""Configurações da aplicação, lidas de variáveis de ambiente ou do arquivo .env."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr = SecretStr("")
    tenant_id: str = "itambe"
    maximo_mcp_url: str = ""
    maximo_api_key: SecretStr = SecretStr("")


def get_settings() -> Settings:
    return Settings()
