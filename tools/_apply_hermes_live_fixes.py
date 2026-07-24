"""Aplica correcciones deterministas para Hermes en vivo y snapshots de Windows."""

# Importa Path para modificar únicamente archivos conocidos del repositorio.
from pathlib import Path


# Sustituye exactamente una aparición y falla si el código cambió.
def replace_once(path: Path, old: str, new: str) -> None:
    """Aplica una sustitución controlada sin ocultar conflictos."""

    # Lee el archivo completo en UTF-8.
    content = path.read_text(encoding="utf-8")
    # Comprueba que el bloque esperado exista una sola vez.
    if content.count(old) != 1:
        raise RuntimeError(f"Bloque inesperado en {path}: {content.count(old)} coincidencias")
    # Sustituye el bloque validado.
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


# Define la raíz del repositorio desde la ubicación de este script.
ROOT = Path(__file__).resolve().parents[1]
# Define el punto de entrada del servicio.
MAIN_PATH = ROOT / "service/src/agent_control_hub/main.py"
# Define el adaptador de Hermes.
HERMES_PATH = ROOT / "service/src/agent_control_hub/adapters/hermes.py"
# Define el agregador de plataformas.
SNAPSHOT_SERVICE_PATH = ROOT / "service/src/agent_control_hub/snapshot_service.py"
# Define las pruebas existentes de Hermes.
HERMES_TEST_PATH = ROOT / "service/tests/test_hermes_adapter.py"


# Añade dependencias estándar para reemplazo resiliente y avisos.
replace_once(
    MAIN_PATH,
    "import argparse\nimport asyncio\nimport time\nfrom pathlib import Path\n",
    "import argparse\nimport asyncio\nimport os\nimport sys\nimport time\nimport uuid\nfrom pathlib import Path\n",
)

# Sustituye la escritura atómica simple por una variante tolerante a bloqueos breves.
replace_once(
    MAIN_PATH,
    '''def write_snapshot_file(path: Path, payload: bytes) -> None:\n    """Sustituye el JSON de salida sin dejar archivos parciales."""\n\n    path.parent.mkdir(parents=True, exist_ok=True)\n    temporary_path = path.with_name(f".{path.name}.tmp")\n    temporary_path.write_bytes(payload)\n    temporary_path.replace(path)\n''',
    '''def write_snapshot_file(path: Path, payload: bytes) -> bool:\n    """Publica el JSON sin terminar el servicio ante bloqueos breves de Windows."""\n\n    # Garantiza que la carpeta de salida exista.\n    path.parent.mkdir(parents=True, exist_ok=True)\n    # Utiliza un temporal único para evitar colisiones con ejecuciones anteriores.\n    temporary_path = path.with_name(\n        f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"\n    )\n    # Escribe primero el contenido completo fuera del archivo servido.\n    temporary_path.write_bytes(payload)\n    try:\n        # Reintenta el reemplazo cuando WAMP, antivirus o navegador bloquean el destino.\n        for attempt in range(8):\n            try:\n                # Sustituye el snapshot de forma atómica cuando Windows lo permite.\n                os.replace(temporary_path, path)\n                # Informa de que la iteración se publicó correctamente.\n                return True\n            except PermissionError:\n                # Conserva el snapshot anterior cuando se agotan los intentos.\n                if attempt == 7:\n                    return False\n                # Aplica una espera progresiva y acotada antes de reintentar.\n                time.sleep(min(0.05 * (attempt + 1), 0.25))\n        # Mantiene una salida explícita para el analizador estático.\n        return False\n    finally:\n        # Elimina el temporal si el reemplazo no llegó a consumirlo.\n        try:\n            temporary_path.unlink(missing_ok=True)\n        except OSError:\n            # Un bloqueo externo del temporal no debe terminar el servicio.\n            pass\n''',
)

# Evita que una iteración bloqueada finalice el bucle completo.
replace_once(
    MAIN_PATH,
    '''            if args.output is not None:\n                write_snapshot_file(args.output, payload)\n            print(payload.decode("utf-8"), end="")\n''',
    '''            if args.output is not None and not write_snapshot_file(args.output, payload):\n                # Conserva la última captura válida y continúa con la siguiente iteración.\n                print(\n                    "[AVISO] snapshot.json está temporalmente bloqueado; "\n                    "se conserva la última captura válida.",\n                    file=sys.stderr,\n                )\n            print(payload.decode("utf-8"), end="")\n''',
)

# Amplía y endurece la sonda del gateway para Hermes Desktop en Windows.
replace_once(
    HERMES_PATH,
    '''        completed = subprocess.run(\n            [executable, "gateway", "status"],\n            capture_output=True,\n            check=False,\n            text=True,\n            timeout=3.0,\n        )\n    # Controla procesos bloqueados o errores del sistema.\n    except (OSError, subprocess.TimeoutExpired):\n        return "unknown"\n''',
    '''        completed = subprocess.run(\n            [executable, "gateway", "status"],\n            capture_output=True,\n            check=False,\n            text=True,\n            encoding="utf-8",\n            errors="replace",\n            timeout=10.0,\n        )\n    # Controla procesos bloqueados o errores del sistema.\n    except (OSError, subprocess.TimeoutExpired, UnicodeError):\n        return "unknown"\n''',
)

# Conserva suficiente texto interno para el objetivo, pero no lo publica sin acotar.
replace_once(
    HERMES_PATH,
    '                content=_sanitize_text(row["content"], 300),\n',
    '                content=_sanitize_text(row["content"], 500),\n',
)

# Acota cada resumen antes de construir ActivityItem, cuyo contrato admite 220 caracteres.
replace_once(
    HERMES_PATH,
    '''        # Añade el evento normalizado.\n        activity.append(\n''',
    '''        # Acota el resumen al contrato público antes de validar el evento.\n        summary = _optional_text(summary, 220)\n        # Añade el evento normalizado.\n        activity.append(\n''',
)

# Acota cada campo de tarea según los límites declarados por Pydantic.
replace_once(
    HERMES_PATH,
    '''        task = TaskInfo(\n            display_name=session.title\n            or (latest_user.content if latest_user is not None else None),\n            conversation_name=session.title,\n            objective=latest_user.content if latest_user is not None else None,\n            status=status,\n            activity=status_message,\n            last_result=latest_assistant.content if latest_assistant is not None else None,\n            started_at=session.started_at,\n            last_activity_at=session.last_activity_at,\n        )\n''',
    '''        task = TaskInfo(\n            display_name=_optional_text(\n                session.title\n                or (latest_user.content if latest_user is not None else None),\n                180,\n            ),\n            conversation_name=_optional_text(session.title, 120),\n            objective=_optional_text(\n                latest_user.content if latest_user is not None else None,\n                500,\n            ),\n            status=status,\n            activity=_optional_text(status_message, 180),\n            last_result=_optional_text(\n                latest_assistant.content if latest_assistant is not None else None,\n                220,\n            ),\n            started_at=session.started_at,\n            last_activity_at=session.last_activity_at,\n        )\n''',
)

# Publica una causa segura cuando un adaptador lanza una excepción inesperada.
replace_once(
    SNAPSHOT_SERVICE_PATH,
    '''                        # Marca la plataforma como fuera de línea.\n                        status=AgentState.OFFLINE,\n                    )\n''',
    '''                        # Marca la plataforma como fuera de línea.\n                        status=AgentState.OFFLINE,\n                        # Distingue un fallo interno de una fuente realmente ausente.\n                        status_reason="adapter_exception",\n                        # Publica solo el tipo de error y nunca su contenido sensible.\n                        status_message=(\n                            f"El adaptador falló durante la captura "\n                            f"({type(result).__name__})."\n                        ),\n                    )\n''',
)

# Añade regresiones para respuestas y resultados de herramienta extensos.
with HERMES_TEST_PATH.open("a", encoding="utf-8") as test_file:
    test_file.write(
        '''\n\n# Valida que mensajes extensos no conviertan Hermes en offline por validación.\ndef test_truncates_long_messages_to_public_contract(tmp_path: Path) -> None:\n    """Acota objetivo, resultado y actividad antes de construir modelos Pydantic."""\n\n    # Crea una carpeta Hermes aislada.\n    hermes_home = tmp_path / "hermes"\n    # Prepara la carpeta de datos.\n    hermes_home.mkdir()\n    # Crea el esquema temporal.\n    connection = _create_database(hermes_home / "state.db")\n    # Define una sesión reciente.\n    now = time.time()\n    # Inserta la sesión de prueba.\n    _insert_session(connection, now - 10, title="Prueba de respuesta extensa")\n    # Inserta una solicitud mayor que el límite de display_name.\n    connection.execute(\n        """\n        INSERT INTO messages (\n            session_id, role, content, timestamp, finish_reason, active, compacted\n        ) VALUES (?, ?, ?, ?, ?, ?, ?)\n        """,\n        (\n            "20260724_113225_5c7a60",\n            "user",\n            "SOLICITUD_EXTENSA_" + ("x" * 700),\n            now - 5,\n            None,\n            1,\n            0,\n        ),\n    )\n    # Inserta una respuesta mayor que el límite de last_result y actividad.\n    connection.execute(\n        """\n        INSERT INTO messages (\n            session_id, role, content, timestamp, finish_reason, active, compacted\n        ) VALUES (?, ?, ?, ?, ?, ?, ?)\n        """,\n        (\n            "20260724_113225_5c7a60",\n            "assistant",\n            "RESPUESTA_EXTENSA_" + ("y" * 700),\n            now,\n            "stop",\n            1,\n            0,\n        ),\n    )\n    # Guarda los cambios.\n    connection.commit()\n    # Cierra la conexión de preparación.\n    connection.close()\n\n    # Ejecuta el adaptador con una sonda determinista.\n    snapshot = asyncio.run(\n        HermesAdapter(\n            hermes_home=hermes_home,\n            gateway_probe=lambda: "stopped",\n        ).collect()\n    )\n\n    # Confirma que la sesión no se degrada a offline.\n    assert snapshot.status == AgentState.COMPLETED\n    # Confirma que la tarea se ha construido.\n    assert snapshot.task is not None\n    # Respeta el máximo público del nombre visible.\n    assert snapshot.task.display_name is not None\n    assert len(snapshot.task.display_name) <= 180\n    # Respeta el máximo público del objetivo.\n    assert snapshot.task.objective is not None\n    assert len(snapshot.task.objective) <= 500\n    # Respeta el máximo público del resultado.\n    assert snapshot.task.last_result is not None\n    assert len(snapshot.task.last_result) <= 220\n    # Todas las actividades respetan el mismo contrato.\n    assert all(\n        item.summary is None or len(item.summary) <= 220\n        for item in snapshot.recent_activity\n    )\n\n\n# Valida que una salida extensa de herramienta permanece observable.\ndef test_truncates_long_tool_result_without_losing_working_state(tmp_path: Path) -> None:\n    """Publica tool_result_pending y acota la salida extensa de terminal."""\n\n    # Crea una carpeta Hermes aislada.\n    hermes_home = tmp_path / "hermes"\n    # Prepara la carpeta de datos.\n    hermes_home.mkdir()\n    # Crea el esquema temporal.\n    connection = _create_database(hermes_home / "state.db")\n    # Define una sesión reciente.\n    now = time.time()\n    # Inserta la sesión de prueba.\n    _insert_session(connection, now - 10, title="Prueba de herramienta extensa")\n    # Inserta el resultado de terminal todavía pendiente de respuesta final.\n    connection.execute(\n        """\n        INSERT INTO messages (\n            session_id, role, content, tool_name, timestamp, finish_reason, active, compacted\n        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)\n        """,\n        (\n            "20260724_113225_5c7a60",\n            "tool",\n            "HERMES_TOOL_START " + ("z" * 700) + " HERMES_TOOL_END",\n            "terminal",\n            now,\n            None,\n            1,\n            0,\n        ),\n    )\n    # Guarda los cambios.\n    connection.commit()\n    # Cierra la conexión de preparación.\n    connection.close()\n\n    # Ejecuta el adaptador.\n    snapshot = asyncio.run(\n        HermesAdapter(\n            hermes_home=hermes_home,\n            gateway_probe=lambda: "running",\n        ).collect()\n    )\n\n    # Mantiene el estado de trabajo mientras Hermes procesa el resultado.\n    assert snapshot.status == AgentState.WORKING\n    # Expone la causa normalizada correspondiente.\n    assert snapshot.status_reason == "tool_result_pending"\n    # Publica la actividad sin superar el contrato.\n    assert snapshot.recent_activity\n    assert snapshot.recent_activity[0].summary is not None\n    assert len(snapshot.recent_activity[0].summary) <= 220\n'''
    )
