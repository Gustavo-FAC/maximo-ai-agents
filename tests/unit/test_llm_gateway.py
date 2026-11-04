import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from maximo_agents.config.settings import Settings
from maximo_agents.llm.gateway import PROVIDERS, LLMConfigError, create_chat_model

SECRET = "sk-ant-teste-123"  # noqa: S105 (valor falso de teste)


def settings(**values) -> Settings:
    # _env_file=None: o teste não lê o .env da máquina.
    return Settings(_env_file=None, **values)


def test_provedores_suportados():
    assert PROVIDERS == ("anthropic", "ollama")


def test_anthropic_usa_configuracao():
    model = create_chat_model(
        settings(
            llm_provider="anthropic",
            llm_model="claude-sonnet-5-5",
            anthropic_api_key=SECRET,
            llm_max_tokens=1000,
        )
    )
    assert isinstance(model, ChatAnthropic)
    assert model.model == "claude-sonnet-5-5"
    assert model.temperature == 0.0
    assert model.max_tokens == 1000
    assert model.anthropic_api_key.get_secret_value() == SECRET
    assert SECRET not in repr(model) + str(model)


def test_anthropic_sem_chave():
    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY"):
        create_chat_model(settings(llm_provider="anthropic", llm_model="claude-sonnet-5-5"))


def test_ollama_usa_configuracao():
    model = create_chat_model(settings(llm_provider="Ollama", llm_model="qwen2.5:7b"))
    assert isinstance(model, ChatOllama)
    assert model.model == "qwen2.5:7b"
    assert model.base_url == "http://localhost:11434"
    assert model.num_predict == 4096


def test_ollama_url_configurada():
    model = create_chat_model(
        settings(llm_provider="ollama", llm_model="qwen2.5:7b", llm_base_url="http://gpu:11434")
    )
    assert model.base_url == "http://gpu:11434"


@pytest.mark.parametrize("provider", ["", "openai", "anthropic ;", "fake"])
def test_provedor_invalido(provider):
    with pytest.raises(LLMConfigError, match="LLM_PROVIDER"):
        create_chat_model(settings(llm_provider=provider, llm_model="x"))


def test_modelo_obrigatorio():
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        create_chat_model(settings(llm_provider="ollama", llm_model=" "))


def test_erro_nao_mostra_chave():
    with pytest.raises(LLMConfigError) as erro:
        create_chat_model(settings(llm_provider="x", anthropic_api_key=SECRET))
    assert SECRET not in str(erro.value)


def test_modelo_falso_tem_a_mesma_interface():
    # Base dos testes do agente sem chave nem Ollama.
    fake = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    assert fake.invoke("oi").content == "ok"
