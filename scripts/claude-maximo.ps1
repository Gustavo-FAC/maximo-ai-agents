# Abre o Claude Code com MAXIMO_MCP_URL e MAXIMO_API_KEY carregados do .env.
# As variáveis ficam só neste processo; a chave não aparece na tela.
#
# Uso (na raiz do repositório):
#   .\scripts\claude-maximo.ps1

$envFile = Join-Path $PSScriptRoot "..\.env"
if (-not (Test-Path $envFile)) {
    Write-Error "Arquivo .env não encontrado na raiz do repositório."
    exit 1
}

foreach ($line in Get-Content $envFile) {
    if ($line -match '^\s*(MAXIMO_MCP_URL|MAXIMO_API_KEY)\s*=\s*(.*)\s*$') {
        $value = $Matches[2].Trim().Trim('"').Trim("'")
        [Environment]::SetEnvironmentVariable($Matches[1], $value, "Process")
    }
}

if (-not $env:MAXIMO_MCP_URL -or -not $env:MAXIMO_API_KEY) {
    Write-Error "Preencha MAXIMO_MCP_URL e MAXIMO_API_KEY no .env."
    exit 1
}

claude @args
