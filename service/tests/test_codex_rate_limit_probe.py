"""Pruebas de la sonda oficial de cuotas de Codex."""

# Importa flujos de texto para simular stdin y stdout de app-server.
import io
# Importa tipos flexibles para el doble de subprocess.Popen.
from typing import Any

# Importa el módulo completo para sustituir dependencias locales.
from agent_control_hub import codex_rate_limit_probe as probe_module
# Importa la clase pública y el normalizador sometidos a prueba.
from agent_control_hub.codex_rate_limit_probe import CodexRateLimitProbe, normalize_rate_limits


# Simula un proceso app-server con respuestas JSONL deterministas.
class _FakeProcess:
    """Expone los canales y métodos mínimos utilizados por la sonda."""

    # Prepara stdin vacío y stdout con las dos respuestas esperadas.
    def __init__(self) -> None:
        """Construye una conversación de inicialización y lectura de cuotas."""

        # Conserva las solicitudes enviadas por la implementación.
        self.stdin = io.StringIO()
        # Publica primero la inicialización y después la cuota real.
        self.stdout = io.StringIO(
            # Une dos mensajes JSON-RPC delimitados por línea.
            '{"id":1,"result":{"userAgent":"codex"}}\n'
            '{"id":2,"result":{"rateLimits":'
            '{"limitId":"codex","planType":"plus",'
            '"primary":{"usedPercent":0,"windowDurationMins":300,'
            '"resetsAt":1785322523},'
            '"secondary":{"usedPercent":12,"windowDurationMins":10080,'
            '"resetsAt":1785408923}}}}\n'
        )
        # Registra si se solicitó la terminación ordenada.
        self.terminated = False
        # Registra si fue necesario forzar el cierre.
        self.killed = False

    # Simula la terminación ordenada del proceso.
    def terminate(self) -> None:
        """Marca el cierre solicitado por finally."""

        # Conserva la señal para comprobar la limpieza.
        self.terminated = True

    # Simula una espera completada inmediatamente.
    def wait(self, timeout: float | None = None) -> int:
        """Devuelve un código de salida correcto."""

        # Ignora el timeout porque el doble siempre finaliza.
        del timeout
        # Informa de una terminación correcta.
        return 0

    # Simula el cierre forzado cuando fuera necesario.
    def kill(self) -> None:
        """Marca la terminación forzada del doble."""

        # Conserva la señal para depuración de la prueba.
        self.killed = True


# Comprueba que la respuesta oficial se transforma al contrato interno.
def test_normalize_rate_limits_converts_camel_case() -> None:
    """Admite el formato account/rateLimits/read documentado por Codex."""

    # Normaliza una cuota con dos ventanas reales.
    normalized = normalize_rate_limits(
        # Proporciona la nomenclatura camelCase oficial.
        {
            "limitId": "codex",
            "planType": "plus",
            "primary": {
                "usedPercent": 25,
                "windowDurationMins": 300,
                "resetsAt": 1_785_322_523,
            },
            "secondary": {
                "usedPercent": 40,
                "windowDurationMins": 10_080,
                "resetsAt": 1_785_408_923,
            },
        }
    )

    # Confirma que existe un resultado utilizable.
    assert normalized is not None
    # Confirma la identidad de la cuota.
    assert normalized["limit_id"] == "codex"
    # Confirma el plan de la cuenta.
    assert normalized["plan_type"] == "plus"
    # Recupera la ventana primaria normalizada.
    primary = normalized["primary"]
    # Confirma que la ventana primaria mantiene una estructura de objeto.
    assert isinstance(primary, dict)
    # Comprueba el porcentaje decimal normalizado.
    assert primary["used_percent"] == 25.0
    # Comprueba la duración normalizada.
    assert primary["window_minutes"] == 300


# Comprueba el intercambio completo con un app-server simulado.
def test_probe_reads_live_rate_limits(monkeypatch: Any) -> None:
    """Inicializa la conexión, consulta la cuota y cierra el proceso."""

    # Crea el proceso determinista utilizado por el doble de Popen.
    fake_process = _FakeProcess()

    # Sustituye la resolución del ejecutable por una ruta controlada.
    monkeypatch.setattr(probe_module.shutil, "which", lambda _name: "codex.exe")
    # Sustituye Popen por el proceso local sin ejecutar binarios.
    monkeypatch.setattr(probe_module.subprocess, "Popen", lambda *_args, **_kwargs: fake_process)

    # Ejecuta la consulta pública con un timeout breve.
    result = CodexRateLimitProbe(timeout_seconds=1.0).read()

    # Confirma que la sonda devolvió una cuota válida.
    assert result is not None
    # Recupera la ventana primaria observada en vivo.
    primary = result["primary"]
    # Confirma que la ventana conserva un objeto normalizado.
    assert isinstance(primary, dict)
    # Comprueba que el restablecimiento se detectó con uso cero.
    assert primary["used_percent"] == 0.0
    # Confirma que el proceso fue cerrado tras obtener la respuesta.
    assert fake_process.terminated is True
    # Confirma que no fue necesario forzar el cierre.
    assert fake_process.killed is False
    # Recupera las solicitudes escritas por la implementación.
    requests = fake_process.stdin.getvalue()
    # Comprueba que se utilizó el método oficial de lectura.
    assert "account/rateLimits/read" in requests
