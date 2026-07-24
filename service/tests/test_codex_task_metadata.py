"""Pruebas de conversación, objetivo, resultado y pendiente de Codex."""

import asyncio
import shutil
from pathlib import Path

from agent_control_hub.adapters.codex import CodexAdapter
from agent_control_hub.models import AgentState

_FIXTURES = Path(__file__).parent / "fixtures" / "codex"


def test_internal_goal_context_is_not_exposed_as_task_title(tmp_path: Path) -> None:
    """Descarta el envoltorio interno y conserva únicamente información útil."""

    # Define el archivo de sesión temporal que procesará el adaptador.
    session = tmp_path / "rollout-goal-context.jsonl"
    # Copia el caso realista sin modificar el fixture compartido.
    shutil.copyfile(_FIXTURES / "goal_context.jsonl", session)

    # Ejecuta la captura asíncrona mediante la API pública del adaptador.
    snapshot = asyncio.run(CodexAdapter(sessions_dir=tmp_path).collect())

    # Verifica que el límite agotado se representa como espera y no como inactividad.
    assert snapshot.status == AgentState.WAITING
    # Verifica que la causa normalizada sigue siendo el límite oficial de Codex.
    assert snapshot.status_reason == "usage_limit_exceeded"
    # Garantiza que existe información estructurada de tarea.
    assert snapshot.task is not None
    # Conserva el título oficial cuando la sesión lo proporciona.
    assert snapshot.task.conversation_name == "Leer objetivo Codex"
    # Utiliza el título oficial como nombre principal de la conversación.
    assert snapshot.task.display_name == "Leer objetivo Codex"
    # Expone el objetivo limpio sin instrucciones internas de continuidad.
    assert snapshot.task.objective == (
        "Auditar técnicamente la aplicación Prometeo antes de producción. "
        "Probar las rutas principales y corregir bloqueantes."
    )
    # Mantiene el último resultado técnico anterior al bloqueo de cuota.
    assert snapshot.task.last_result is not None
    # Comprueba que el resultado conserva la cobertura observada.
    assert "174/174" in snapshot.task.last_result
    # Conserva el pendiente operativo separado del estado actual.
    assert snapshot.task.pending is not None
    # Sustituye la ruta local antes de publicar el pendiente.
    assert "[ruta]" in snapshot.task.pending
    # Impide que el envoltorio interno llegue al contrato público.
    serialized = snapshot.model_dump_json()
    # Verifica que la plantilla de continuidad no se publica.
    assert "Continue working toward the active thread goal" not in serialized
    # Verifica que la ruta absoluta de Windows tampoco se publica.
    assert r"C:\wamp64" not in serialized


def test_objective_generates_deterministic_title_without_official_conversation_name(
    tmp_path: Path,
) -> None:
    """Genera un título breve únicamente cuando Codex no ofrece título oficial."""

    # Define una sesión mínima sin conversation_title.
    session = tmp_path / "rollout-objective-only.jsonl"
    # Escribe metadatos, objetivo y tarea activa en orden temporal.
    session.write_text(
        "\n".join(
            [
                '{"timestamp":"2026-07-23T20:00:00Z","type":"session_meta",'
                '"payload":{"session_id":"objective-only","timestamp":'
                '"2026-07-23T20:00:00Z","cwd":"C:\\\\dev\\\\Prometeo"}}',
                '{"timestamp":"2026-07-23T20:00:01Z","type":"event_msg",'
                '"payload":{"type":"thread_goal_updated","goal":{"objective":'
                '"Auditar técnicamente Prometeo. Revisar seguridad y pruebas."}}}',
                '{"timestamp":"2026-07-23T20:00:02Z","type":"event_msg",'
                '"payload":{"type":"task_started"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Captura el estado de la sesión mínima.
    snapshot = asyncio.run(CodexAdapter(sessions_dir=tmp_path).collect())

    # Garantiza que la tarea está disponible.
    assert snapshot.task is not None
    # No inventa un título oficial que la fuente no ha proporcionado.
    assert snapshot.task.conversation_name is None
    # Deriva el nombre visible de la primera frase del objetivo.
    assert snapshot.task.display_name == "Auditar técnicamente Prometeo."
    # Conserva también el objetivo completo para la interfaz detallada.
    assert snapshot.task.objective == (
        "Auditar técnicamente Prometeo. Revisar seguridad y pruebas."
    )
