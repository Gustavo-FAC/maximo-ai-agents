"""Gateway de LLM: cria o modelo de chat (LangChain) a partir da configuração.

O resto do código só conhece ``BaseChatModel`` (``invoke``, ``bind_tools``); trocar de
LLM é trocar ``LLM_PROVIDER``/``LLM_MODEL`` no ``.env``. Provedores novos (Azure OpenAI,
Bedrock, Vertex, watsonx) entram como mais um ramo em ``_BUILDERS``.

Uso:
    from maximo_agents.llm.gateway import create_chat_model
    model = create_chat_model()
"""

from collections.abc import Callable

from langchain_core.language_models import BaseChatModel

from maximo_agents.config.settings import Settings, get_settings

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class LLMConfigError(ValueError):
    """Configuração de LLM inválida. A mensagem nunca contém segredos."""


def _anthropic(settings: Settings) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    if not settings.anthropic_api_key.get_secret_value():
        raise LLMConfigError("Preencha ANTHROPIC_API_KEY no .env para LLM_PROVIDER=anthropic.")
    return ChatAnthropic(
        model=settings.llm_model,
        api_key=settings.anthropic_api_key,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
    )


def _ollama(settings: Settings) -> BaseChatModel:
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.llm_model,
        base_url=settings.llm_base_url or DEFAULT_OLLAMA_URL,
        temperature=settings.llm_temperature,
        num_predict=settings.llm_max_tokens,
        client_kwargs={"timeout": settings.llm_timeout_seconds},
    )


_BUILDERS: dict[str, Callable[[Settings], BaseChatModel]] = {
    "anthropic": _anthropic,
    "ollama": _ollama,
}

PROVIDERS = tuple(_BUILDERS)


def create_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Modelo de chat do provedor configurado (LLM_PROVIDER, LLM_MODEL)."""
    settings = settings or get_settings()
    provider = settings.llm_provider.strip().lower()
    if provider not in _BUILDERS:
        raise LLMConfigError(
            f"LLM_PROVIDER inválido: '{settings.llm_provider}'. Use um de: {', '.join(PROVIDERS)}."
        )
    if not settings.llm_model.strip():
        raise LLMConfigError("Preencha LLM_MODEL no .env.")
    return _BUILDERS[provider](settings)
