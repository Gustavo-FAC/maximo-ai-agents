"""Primeiro marco: conecta ao MCP Server do Maximo e lista as ferramentas disponíveis.

Uso:
    uv run python -m maximo_agents.mcp.check_connection
"""

import asyncio
import sys

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from maximo_agents.config.settings import get_settings


async def main() -> int:
    settings = get_settings()
    if not settings.maximo_mcp_url or not settings.maximo_api_key.get_secret_value():
        print("Preencha MAXIMO_MCP_URL e MAXIMO_API_KEY no arquivo .env")
        return 1

    headers = {"apikey": settings.maximo_api_key.get_secret_value()}
    print(f"Conectando ao MCP Server do tenant '{settings.tenant_id}'...")

    async with create_mcp_http_client(headers=headers) as http_client:
        async with streamable_http_client(settings.maximo_mcp_url, http_client=http_client) as (
            read,
            write,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()

    print(f"Conexão OK. {len(result.tools)} ferramentas disponíveis:\n")
    for tool in sorted(result.tools, key=lambda t: t.name):
        read_only = tool.annotations.read_only_hint if tool.annotations else None
        marca = "leitura" if read_only else "VERIFICAR"
        print(f"  [{marca:9}] {tool.name}")
        if tool.description:
            print(f"              {tool.description.strip()[:300]}")
        parametros = (tool.input_schema or {}).get("properties", {})
        if parametros:
            print(f"              parâmetros: {', '.join(parametros)}")
    print("\nAtenção: a marcação de leitura vem do servidor e não é garantia.")
    print("A allowlist dos agentes deve ser definida manualmente.")
    return 0


if __name__ == "__main__":
    # Console do Windows usa cp1252 por padrão e quebra os acentos
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(asyncio.run(main()))
    except Exception as erro:  # noqa: BLE001
        print(f"Falha na conexão com o MCP Server: {erro!r}")
        print("Verifique a URL da rota, a chave de API e o acesso de rede ao OpenShift.")
        sys.exit(1)
