# Detiene la ejecución cuando se produce cualquier error.
$ErrorActionPreference = "Stop"

# Calcula la raíz del repositorio a partir de este script.
$RepositoryRoot = Split-Path -Parent $PSScriptRoot

# Cambia al directorio del servicio local.
Set-Location "$RepositoryRoot\service"

# Crea el entorno virtual cuando todavía no existe.
if (-not (Test-Path ".venv")) {
    # Inicializa un entorno aislado para las dependencias.
    python -m venv .venv
}

# Activa el entorno virtual del proyecto.
& ".venv\Scripts\Activate.ps1"

# Instala el servicio y sus herramientas de desarrollo.
python -m pip install -e ".[dev]"

# Ejecuta una instantánea simulada para validar la instalación.
agent-control --once --mock
