"""Pruebas del adaptador local y de solo lectura de Hermes."""

# Importa asyncio para ejecutar la interfaz pública del adaptador.
import asyncio

# Importa JSON para crear configuraciones equivalentes a Hermes.
import json

# Importa SQLite para generar una base de prueba aislada.
import sqlite3

# Importa tiempo Unix para construir sesiones recientes.
import time

# Importa Path para trabajar exclusivamente dentro de tmp_path.
from pathlib import Path

# Importa el adaptador que se valida.
from agent_control_hub.adapters.hermes import HermesAdapter

# Importa los estados normalizados esperados.
from agent_control_hub.models import AgentState


# Crea el esquema mínimo compatible con la versión 16 observada.
def _create_database(path: Path) -> sqlite3.Connection:
    """Genera tablas de sesiones y mensajes sin datos sensibles."""

    # Abre una base temporal controlada por pytest.
    connection = sqlite3.connect(path)
    # Crea la tabla de sesiones con las columnas leídas por el adaptador.
    connection.execute(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            source TEXT,
            model TEXT,
            model_config TEXT,
            started_at REAL,
            ended_at REAL,
            end_reason TEXT,
            message_count INTEGER,
            tool_call_count INTEGER,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            cache_write_tokens INTEGER,
            reasoning_tokens INTEGER,
            cwd TEXT,
            billing_provider TEXT,
            estimated_cost_usd REAL,
            actual_cost_usd REAL,
            cost_status TEXT,
            title TEXT,
            api_call_count INTEGER,
            handoff_error TEXT,
            archived INTEGER DEFAULT 0
        )
        """
    )
    # Crea la tabla de mensajes con los campos visibles y de actividad.
    connection.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT,
            tool_name TEXT,
            tool_calls TEXT,
            timestamp REAL NOT NULL,
            finish_reason TEXT,
            active INTEGER,
            compacted INTEGER DEFAULT 0
        )
        """
    )
    # Devuelve la conexión para insertar el escenario de cada prueba.
    return connection


# Inserta una sesión completa con los contadores observados en Hermes.
def _insert_session(
    connection: sqlite3.Connection,
    started_at: float,
    title: str = "Saludo amistoso en español",
) -> None:
    """Añade una sesión TUI con modelo gratuito y proyecto sanitizable."""

    # Construye únicamente claves seguras de configuración.
    model_config = json.dumps(
        {
            "model": "tencent/hy3:free",
            "provider": "nous",
            "api_mode": "chat_completions",
        }
    )
    # Inserta la sesión sin system_prompt ni credenciales.
    connection.execute(
        """
        INSERT INTO sessions (
            id, source, model, model_config, started_at, ended_at, end_reason,
            message_count, tool_call_count, input_tokens, output_tokens,
            cache_read_tokens, cache_write_tokens, reasoning_tokens, cwd,
            billing_provider, estimated_cost_usd, actual_cost_usd, cost_status,
            title, api_call_count, handoff_error, archived
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "tui",
            "tencent/hy3:free",
            model_config,
            started_at,
            None,
            None,
            2,
            0,
            37768,
            238,
            19840,
            0,
            0,
            r"C:\Users\private\Projects\Agent Control Hub",
            "nous",
            0.0,
            None,
            "estimated",
            title,
            3,
            None,
            0,
        ),
    )


# Valida una sesión respondida y todos sus metadatos seguros.
def test_collects_latest_hermes_session_from_read_only_sqlite(tmp_path: Path) -> None:
    """Publica título, modelo, tokens, proyecto, costes y mensajes sanitizados."""

    # Define la carpeta equivalente a HERMES_HOME.
    hermes_home = tmp_path / "hermes"
    # Crea la carpeta local aislada.
    hermes_home.mkdir()
    # Crea la carpeta cron para verificar un contador vacío.
    (hermes_home / "cron").mkdir()
    # Define la base de datos temporal.
    database_path = hermes_home / "state.db"
    # Abre y prepara el esquema.
    connection = _create_database(database_path)
    # Calcula una sesión reciente para que se marque completada.
    now = time.time()
    # Inserta la sesión principal.
    _insert_session(connection, now - 30)
    # Inserta la solicitud del usuario con una ruta que debe ocultarse.
    connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "user",
            r"Revisa C:\Users\private\secret.txt",
            now - 20,
            None,
            1,
            0,
        ),
    )
    # Inserta la respuesta final del asistente.
    connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "assistant",
            "La comprobación terminó correctamente.",
            now - 10,
            "stop",
            1,
            0,
        ),
    )
    # Guarda los datos de prueba.
    connection.commit()
    # Cierra la conexión de escritura antes de ejecutar el adaptador.
    connection.close()
    # Añade una ventana conocida para el modelo actual.
    (hermes_home / "context_length_cache.yaml").write_text(
        "'tencent/hy3:free':\n  context_length: 262144\n",
        encoding="utf-8",
    )

    # Ejecuta la captura mediante la API pública.
    snapshot = asyncio.run(
        HermesAdapter(
            hermes_home=hermes_home,
            gateway_probe=lambda: "stopped",
        ).collect()
    )

    # Confirma el identificador estable de la plataforma.
    assert snapshot.platform_id == "hermes"
    # Confirma que una respuesta reciente se considera completada.
    assert snapshot.status == AgentState.COMPLETED
    # Confirma el título oficial de la sesión.
    assert snapshot.task is not None
    # Comprueba el nombre visible de la conversación.
    assert snapshot.task.conversation_name == "Saludo amistoso en español"
    # Comprueba que la última solicitud se conserva sanitizada.
    assert snapshot.task.objective is not None
    # Verifica que la ruta privada no se publica.
    assert r"C:\Users\private" not in snapshot.task.objective
    # Verifica que se utiliza el marcador público de ruta.
    assert "[ruta]" in snapshot.task.objective
    # Comprueba que la última respuesta se conserva como resultado.
    assert snapshot.task.last_result == "La comprobación terminó correctamente."
    # Confirma los metadatos de sesión y modelo.
    assert snapshot.session is not None
    # Comprueba el modelo realmente guardado por Hermes.
    assert snapshot.session.model_name == "tencent/hy3:free"
    # Comprueba el proveedor de la sesión.
    assert snapshot.session.model_provider == "nous"
    # Confirma el alias de proyecto sin ruta absoluta.
    assert snapshot.project is not None
    # Comprueba el último segmento de cwd.
    assert snapshot.project.display_name == "Agent Control Hub"
    # Confirma los contadores de tokens.
    assert snapshot.token_usage is not None
    # Comprueba la entrada acumulada.
    assert snapshot.token_usage.input_tokens == 37768
    # Comprueba la caché de entrada.
    assert snapshot.token_usage.cached_input_tokens == 19840
    # Comprueba la ventana leída desde la caché local.
    assert snapshot.token_usage.model_context_window == 262144
    # Confirma los metadatos operativos.
    assert snapshot.runtime is not None
    # Comprueba el gateway detenido observado por la sonda.
    assert snapshot.runtime.gateway_status == "stopped"
    # Comprueba el coste estimado gratuito.
    assert snapshot.runtime.estimated_cost_usd == 0.0
    # Garantiza que la base sigue existiendo tras la lectura.
    assert database_path.is_file()


# Valida una solicitud pendiente sin respuesta del asistente.
def test_marks_latest_user_message_as_working(tmp_path: Path) -> None:
    """Distingue una petición pendiente de una sesión inactiva."""

    # Crea la carpeta de datos temporal.
    hermes_home = tmp_path / "hermes"
    # Prepara la estructura local.
    hermes_home.mkdir()
    # Define la base de prueba.
    database_path = hermes_home / "state.db"
    # Crea el esquema mínimo.
    connection = _create_database(database_path)
    # Obtiene una fecha reciente.
    now = time.time()
    # Inserta la sesión.
    _insert_session(connection, now - 5, title="Trabajo pendiente")
    # Inserta únicamente el mensaje del usuario.
    connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "user",
            "Analiza el proyecto actual.",
            now,
            None,
            1,
            0,
        ),
    )
    # Guarda los datos.
    connection.commit()
    # Cierra la conexión de preparación.
    connection.close()

    # Ejecuta el adaptador con gateway conocido.
    snapshot = asyncio.run(
        HermesAdapter(
            hermes_home=hermes_home,
            gateway_probe=lambda: "running",
        ).collect()
    )

    # Confirma el estado de trabajo real.
    assert snapshot.status == AgentState.WORKING
    # Confirma la causa normalizada.
    assert snapshot.status_reason == "response_pending"
    # Confirma que no se inventan agentes secundarios.
    assert snapshot.active_agents == 0
    # Confirma el estado real del gateway.
    assert snapshot.runtime is not None
    # Comprueba el valor devuelto por la sonda inyectada.
    assert snapshot.runtime.gateway_status == "running"


# Valida el comportamiento cuando Hermes no está instalado.
def test_reports_offline_when_state_database_is_missing(tmp_path: Path) -> None:
    """Devuelve offline sin crear archivos o carpetas automáticamente."""

    # Define una carpeta que no contiene state.db.
    hermes_home = tmp_path / "missing-hermes"

    # Ejecuta la captura sobre la ruta inexistente.
    snapshot = asyncio.run(HermesAdapter(hermes_home=hermes_home).collect())

    # Confirma el estado sin conexión.
    assert snapshot.status == AgentState.OFFLINE
    # Confirma una causa estable y accionable.
    assert snapshot.status_reason == "state_db_unavailable"
    # Garantiza que el adaptador no creó la carpeta.
    assert not hermes_home.exists()


# Valida que mensajes extensos no conviertan Hermes en offline por validación.
def test_truncates_long_messages_to_public_contract(tmp_path: Path) -> None:
    """Acota objetivo, resultado y actividad antes de construir modelos Pydantic."""

    # Crea una carpeta Hermes aislada.
    hermes_home = tmp_path / "hermes"
    # Prepara la carpeta de datos.
    hermes_home.mkdir()
    # Crea el esquema temporal.
    connection = _create_database(hermes_home / "state.db")
    # Define una sesión reciente.
    now = time.time()
    # Inserta la sesión de prueba.
    _insert_session(connection, now - 10, title="Prueba de respuesta extensa")
    # Inserta una solicitud mayor que el límite de display_name.
    connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "user",
            "SOLICITUD_EXTENSA_" + ("x" * 700),
            now - 5,
            None,
            1,
            0,
        ),
    )
    # Inserta una respuesta mayor que el límite de last_result y actividad.
    connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "assistant",
            "RESPUESTA_EXTENSA_" + ("y" * 700),
            now,
            "stop",
            1,
            0,
        ),
    )
    # Guarda los cambios.
    connection.commit()
    # Cierra la conexión de preparación.
    connection.close()

    # Ejecuta el adaptador con una sonda determinista.
    snapshot = asyncio.run(
        HermesAdapter(
            hermes_home=hermes_home,
            gateway_probe=lambda: "stopped",
        ).collect()
    )

    # Confirma que la sesión no se degrada a offline.
    assert snapshot.status == AgentState.COMPLETED
    # Confirma que la tarea se ha construido.
    assert snapshot.task is not None
    # Respeta el máximo público del nombre visible.
    assert snapshot.task.display_name is not None
    assert len(snapshot.task.display_name) <= 180
    # Respeta el máximo público del objetivo.
    assert snapshot.task.objective is not None
    assert len(snapshot.task.objective) <= 500
    # Respeta el máximo público del resultado.
    assert snapshot.task.last_result is not None
    assert len(snapshot.task.last_result) <= 220
    # Todas las actividades respetan el mismo contrato.
    assert all(
        item.summary is None or len(item.summary) <= 220 for item in snapshot.recent_activity
    )


# Valida que una salida extensa de herramienta permanece observable.
def test_truncates_long_tool_result_without_losing_working_state(tmp_path: Path) -> None:
    """Publica tool_result_pending y acota la salida extensa de terminal."""

    # Crea una carpeta Hermes aislada.
    hermes_home = tmp_path / "hermes"
    # Prepara la carpeta de datos.
    hermes_home.mkdir()
    # Crea el esquema temporal.
    connection = _create_database(hermes_home / "state.db")
    # Define una sesión reciente.
    now = time.time()
    # Inserta la sesión de prueba.
    _insert_session(connection, now - 10, title="Prueba de herramienta extensa")
    # Inserta el resultado de terminal todavía pendiente de respuesta final.
    connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, tool_name, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "tool",
            "HERMES_TOOL_START " + ("z" * 700) + " HERMES_TOOL_END",
            "terminal",
            now,
            None,
            1,
            0,
        ),
    )
    # Guarda los cambios.
    connection.commit()
    # Cierra la conexión de preparación.
    connection.close()

    # Ejecuta el adaptador.
    snapshot = asyncio.run(
        HermesAdapter(
            hermes_home=hermes_home,
            gateway_probe=lambda: "running",
        ).collect()
    )

    # Mantiene el estado de trabajo mientras Hermes procesa el resultado.
    assert snapshot.status == AgentState.WORKING
    # Expone la causa normalizada correspondiente.
    assert snapshot.status_reason == "tool_result_pending"
    # Publica la actividad sin superar el contrato.
    assert snapshot.recent_activity
    assert snapshot.recent_activity[0].summary is not None
    assert len(snapshot.recent_activity[0].summary) <= 220
