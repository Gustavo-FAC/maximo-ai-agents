from maximo_agents.config.settings import Settings


def test_chaves_nao_aparecem_em_texto():
    settings = Settings(maximo_api_key="segredo-123", anthropic_api_key="sk-teste")
    texto = repr(settings) + str(settings)
    assert "segredo-123" not in texto
    assert "sk-teste" not in texto
