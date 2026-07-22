"""Adaptador determinista para desarrollo sin credenciales."""

# Importa fechas conscientes de zona horaria.
from datetime import UTC, datetime, timedelta

# Importa el contrato común de adaptadores.
from agent_control_hub.adapters.base import PlatformAdapter
# Importa los modelos normalizados del servicio.
from agent_control_hub.models import AgentSnapshot, AgentState, PlatformSnapshot


# Implementa una fuente simulada para firmware, documentación y pruebas.
class MockAdapter(PlatformAdapter):
    """Genera una plataforma de demostración estable."""

    # Expone el identificador estable del adaptador.
    @property
    # Declara el tipo de retorno del identificador.
    def platform_id(self) -> str:
        """Devuelve el identificador del adaptador simulado."""

        # Devuelve el nombre interno utilizado por configuración y registros.
        return "mock"

    # Genera una instantánea compatible con el protocolo del dispositivo.
    async def collect(self) -> PlatformSnapshot:
        """Construye datos representativos sin utilizar una API externa."""

        # Captura una única fecha para mantener coherencia temporal.
        now = datetime.now(UTC)
        # Construye la colección de agentes visibles en la pantalla.
        agents = [
            # Simula un agente de desarrollo activo.
            AgentSnapshot(
                # Asigna el identificador estable del primer agente.
                agent_id="seo-python",
                # Asigna el nombre visible del primer agente.
                display_name="SEO Python",
                # Marca el primer agente como activo.
                status=AgentState.WORKING,
                # Describe el objetivo que está ejecutando.
                task_name="Herramienta SEO",
                # Simula una ejecución iniciada hace más de dos horas.
                started_at=now - timedelta(hours=2, minutes=14),
            ),
            # Simula un agente que requiere intervención.
            AgentSnapshot(
                # Asigna el identificador estable del segundo agente.
                agent_id="comparador-cam",
                # Asigna el nombre visible del segundo agente.
                display_name="Comparador CAM",
                # Marca el segundo agente como pendiente.
                status=AgentState.WAITING,
                # Describe la acción necesaria.
                task_name="Esperando autorización",
                # No declara comienzo porque no está ejecutando trabajo.
                started_at=None,
            ),
            # Simula un agente finalizado correctamente.
            AgentSnapshot(
                # Asigna el identificador estable del tercer agente.
                agent_id="prometeo",
                # Asigna el nombre visible del tercer agente.
                display_name="Prometeo",
                # Marca el tercer agente como completado.
                status=AgentState.COMPLETED,
                # Describe la última tarea completada.
                task_name="Pruebas completadas",
                # No declara una tarea activa.
                started_at=None,
            ),
            # Simula una tarea con error visible.
            AgentSnapshot(
                # Asigna el identificador estable de la tarea de pruebas.
                agent_id="tests",
                # Asigna el nombre visible de la tarea.
                display_name="Tests",
                # Marca la tarea como fallida.
                status=AgentState.ERROR,
                # Describe de forma breve el fallo simulado.
                task_name="3 pruebas fallidas",
                # No declara una tarea activa.
                started_at=None,
            ),
        ]
        # Devuelve la plataforma completa de demostración.
        return PlatformSnapshot(
            # Identifica la plataforma como Codex para el prototipo visual.
            platform_id="codex",
            # Define el nombre que muestra el dispositivo.
            display_name="Codex",
            # Declara que existe trabajo activo.
            status=AgentState.WORKING,
            # Simula el consumo diario acumulado.
            tokens_today=184_200,
            # No inventa un coste cuando la cuenta no lo expone.
            cost_today=None,
            # Simula el porcentaje semanal restante.
            weekly_remaining_pct=30,
            # Simula el porcentaje de la ventana corta restante.
            rolling_remaining_pct=72,
            # Simula el próximo reinicio semanal.
            next_reset_at=now + timedelta(days=7),
            # Cuenta únicamente agentes en ejecución.
            active_agents=1,
            # Adjunta la lista de agentes simulados.
            agents=agents,
        )
