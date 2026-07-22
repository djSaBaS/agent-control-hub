# Detiene el script ante cualquier error de publicación.
$ErrorActionPreference = "Stop"

# Calcula la raíz del repositorio a partir del directorio del script.
$RepositoryRoot = Split-Path -Parent $PSScriptRoot

# Cambia al directorio raíz del proyecto.
Set-Location $RepositoryRoot

# Comprueba que GitHub CLI se encuentre instalado.
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    # Detiene el proceso con una instrucción concreta.
    throw "GitHub CLI no está instalado. Instálalo con: winget install --id GitHub.cli"
}

# Comprueba que exista una sesión autenticada en GitHub CLI.
gh auth status

# Crea el repositorio público y publica la rama principal.
gh repo create djSaBaS/agent-control-hub --public --source . --remote origin --push --description "Physical dashboard and local service for monitoring AI agents, quotas, tokens and costs."
