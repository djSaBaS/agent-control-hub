"""Aplica la detección automática de profiles de Hermes de forma determinista."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERMES_PATH = ROOT / "service/src/agent_control_hub/adapters/hermes.py"
TEST_PATH = ROOT / "service/tests/test_hermes_adapter.py"


def replace_once(content: str, old: str, new: str, label: str) -> str:
    """Sustituye exactamente un bloque o detiene la migración."""

    occurrences = content.count(old)
    if occurrences != 1:
        raise RuntimeError(f"Ancla no única para {label}: {occurrences}")
    return content.replace(old, new, 1)


hermes = HERMES_PATH.read_text(encoding="utf-8")

hermes = replace_once(
    hermes,
    '''class _HermesMessage:\n    """Mensaje sanitizable sin razonamiento ni metadatos privados."""\n\n    message_id: int\n    role: str\n    content: str | None\n    tool_name: str | None\n    tool_names: tuple[str, ...]\n    timestamp: datetime\n    finish_reason: str | None\n    active: bool | None\n\n\n# Devuelve la ubicación predeterminada utilizada por Hermes Desktop.\n''',
    '''class _HermesMessage:\n    """Mensaje sanitizable sin razonamiento ni metadatos privados."""\n\n    message_id: int\n    role: str\n    content: str | None\n    tool_name: str | None\n    tool_names: tuple[str, ...]\n    timestamp: datetime\n    finish_reason: str | None\n    active: bool | None\n\n\n# Representa una fuente de estado aislada perteneciente a un profile de Hermes.\n@dataclass(frozen=True, slots=True)\nclass _HermesProfileSource:\n    """Describe un HERMES_HOME sin exponer su ruta absoluta."""\n\n    profile_name: str\n    home: Path\n    database_path: Path\n    is_default: bool\n\n\n# Devuelve la ubicación predeterminada utilizada por Hermes Desktop.\n''',
    "dataclass de profile",
)

hermes = replace_once(
    hermes,
    '''    # Mantiene compatibilidad con instalaciones CLI de Linux y macOS.\n    return Path.home() / ".hermes"\n\n\n# Convierte una marca temporal Unix en una fecha UTC válida.\n''',
    '''    # Mantiene compatibilidad con instalaciones CLI de Linux y macOS.\n    return Path.home() / ".hermes"\n\n\n# Normaliza un nombre de profile sin convertirlo en una ruta pública.\ndef _profile_name(value: object) -> str | None:\n    """Acepta únicamente nombres breves, visibles y sin segmentos especiales."""\n\n    # Reutiliza la normalización textual común.\n    normalized = _optional_text(value, 32)\n    # Rechaza nombres vacíos y segmentos con significado de navegación.\n    if normalized is None or normalized in {".", ".."}:\n        return None\n    # Evita representar separadores como parte del nombre del profile.\n    if "/" in normalized or "\\\\" in normalized:\n        return None\n    # Devuelve el identificador visible validado.\n    return normalized\n\n\n# Descubre el profile predeterminado y los profiles aislados instalados.\ndef _discover_profile_sources(hermes_root: Path) -> list[_HermesProfileSource]:\n    """Busca únicamente state.db en la raíz y en profiles/<nombre>."""\n\n    # Inicializa la colección sin recorrer de forma recursiva rutas arbitrarias.\n    sources: list[_HermesProfileSource] = []\n    # Comprueba la base canónica del profile predeterminado.\n    default_database = hermes_root / "state.db"\n    # Conserva la fuente predeterminada cuando es un archivo real y no un enlace.\n    if default_database.is_file() and not default_database.is_symlink():\n        sources.append(\n            _HermesProfileSource(\n                profile_name="default",\n                home=hermes_root,\n                database_path=default_database,\n                is_default=True,\n            )\n        )\n    # Resuelve el único contenedor oficial de profiles.\n    profiles_root = hermes_root / "profiles"\n    # Devuelve las fuentes encontradas cuando todavía no existe ese contenedor.\n    if not profiles_root.is_dir() or profiles_root.is_symlink():\n        return sources\n    # Recorre únicamente hijos directos para impedir búsquedas amplias o costosas.\n    try:\n        profile_homes = sorted(profiles_root.iterdir(), key=lambda path: path.name.casefold())\n    # Conserva el profile predeterminado cuando Windows niega el listado.\n    except OSError:\n        return sources\n    # Valida cada directorio candidato de forma independiente.\n    for profile_home in profile_homes:\n        # Ignora archivos y enlaces de directorio.\n        if not profile_home.is_dir() or profile_home.is_symlink():\n            continue\n        # Normaliza el nombre sin publicar la ruta completa.\n        name = _profile_name(profile_home.name)\n        # Omite nombres no representables de forma segura.\n        if name is None:\n            continue\n        # Construye la ubicación canónica dentro del profile.\n        database_path = profile_home / "state.db"\n        # Exige una base real y rechaza enlaces a archivos externos.\n        if not database_path.is_file() or database_path.is_symlink():\n            continue\n        # Añade la fuente aislada validada.\n        sources.append(\n            _HermesProfileSource(\n                profile_name=name,\n                home=profile_home,\n                database_path=database_path,\n                is_default=False,\n            )\n        )\n    # Devuelve una lista estable para diagnóstico y pruebas.\n    return sources\n\n\n# Lee el profile preferido por Hermes cuando existe el marcador oficial.\ndef _active_profile_name(hermes_root: Path) -> str | None:\n    """Interpreta active_profile sin aceptar archivos grandes o enlaces."""\n\n    # Localiza el marcador compartido por los comandos profile use.\n    marker = hermes_root / "active_profile"\n    # Rechaza ausencias y enlaces antes de abrir el archivo.\n    if not marker.is_file() or marker.is_symlink():\n        return None\n    # Limita el tamaño para no leer contenido inesperado.\n    try:\n        if marker.stat().st_size > 1024:\n            return None\n        return _profile_name(marker.read_text(encoding="utf-8", errors="replace"))\n    # Ignora fallos de acceso y permite usar la actividad como alternativa.\n    except OSError:\n        return None\n\n\n# Construye el nombre corto mostrado por dashboard y dispositivo.\ndef _profile_display_name(source: _HermesProfileSource) -> str:\n    """Mantiene el nombre histórico para default e identifica profiles nombrados."""\n\n    # Evita modificar la interfaz de instalaciones sin profiles.\n    if source.is_default:\n        return "Hermes Agent"\n    # Acota el nombre completo al límite del contrato público.\n    return _optional_text(f"Hermes · {source.profile_name}", 40) or "Hermes Agent"\n\n\n# Construye una referencia relativa y no sensible a la base seleccionada.\ndef _profile_source_reference(source: _HermesProfileSource) -> str:\n    """Identifica la fuente sin publicar HERMES_HOME ni el usuario de Windows."""\n\n    # Conserva compatibilidad con el valor original.\n    if source.is_default:\n        return "state.db"\n    # Publica únicamente el nombre validado del profile.\n    return f"profiles/{source.profile_name}/state.db"\n\n\n# Convierte una marca temporal Unix en una fecha UTC válida.\n''',
    "descubrimiento de profiles",
)

hermes = replace_once(
    hermes,
    '''def _default_gateway_probe() -> str:\n    """Devuelve running, stopped o unknown sin lanzar un shell."""\n\n    # Localiza la CLI instalada en PATH.\n    executable = shutil.which("hermes")\n''',
    '''def _default_gateway_probe(profile_name: str | None) -> str:\n    """Devuelve running, stopped o unknown sin lanzar un shell."""\n\n    # Localiza la CLI instalada en PATH.\n    executable = shutil.which("hermes")\n''',
    "firma gateway",
)

hermes = replace_once(
    hermes,
    '''        completed = subprocess.run(\n            [executable, "gateway", "status"],\n            capture_output=True,\n''',
    '''        # Construye argumentos separados para impedir interpretación por shell.\n        command = [executable]\n        # Selecciona el mismo profile que aporta la sesión cuando no es default.\n        if profile_name is not None and profile_name != "default":\n            command.extend(["--profile", profile_name])\n        # Añade el único subcomando permitido por esta sonda.\n        command.extend(["gateway", "status"])\n        # Ejecuta la consulta oficial con tiempo máximo.\n        completed = subprocess.run(\n            command,\n            capture_output=True,\n''',
    "comando gateway",
)

hermes = replace_once(
    hermes,
    '''def _build_usage(\n    session: _HermesSession,\n    context_window: int | None,\n) -> UsageBreakdown:\n''',
    '''def _build_usage(\n    session: _HermesSession,\n    context_window: int | None,\n    source_reference: str,\n) -> UsageBreakdown:\n''',
    "firma build usage",
)

hermes = replace_once(
    hermes,
    '        source_reference="state.db",\n',
    '        source_reference=source_reference,\n',
    "referencia de uso",
)

hermes = replace_once(
    hermes,
    '        gateway_probe: Callable[[], str] | None = None,\n',
    '        gateway_probe: Callable[[str | None], str] | None = None,\n',
    "tipo de gateway probe",
)

hermes = replace_once(
    hermes,
    '''        # Resuelve la carpeta de datos efectiva.\n        self._hermes_home = hermes_home or _default_hermes_home()\n        # Construye la ruta canónica de SQLite.\n        self._database_path = self._hermes_home / "state.db"\n''',
    '''        # Resuelve la raíz que contiene default y profiles nombrados.\n        self._hermes_root = hermes_home or _default_hermes_home()\n''',
    "raíz Hermes",
)

hermes = replace_once(
    hermes,
    '''        # Inicializa la fecha de la última consulta.\n        self._gateway_checked_at: datetime | None = None\n''',
    '''        # Inicializa la fecha de la última consulta.\n        self._gateway_checked_at: datetime | None = None\n        # Registra el profile asociado a la caché para no mezclar gateways.\n        self._gateway_profile_name: str | None = None\n''',
    "cache de gateway por profile",
)

hermes = replace_once(
    hermes,
    '''    def _cached_gateway_status(self, now: datetime) -> str:\n        """Evita ejecutar hermes gateway status cada cinco segundos."""\n\n        # Comprueba si la caché sigue vigente.\n        if self._gateway_checked_at is not None and now - self._gateway_checked_at < timedelta(\n            seconds=_GATEWAY_CACHE_SECONDS\n        ):\n            return self._gateway_status\n        # Ejecuta la sonda controlada.\n        self._gateway_status = self._gateway_probe()\n        # Guarda la fecha de actualización.\n        self._gateway_checked_at = now\n        # Devuelve el estado observado.\n        return self._gateway_status\n''',
    '''    def _cached_gateway_status(self, now: datetime, profile_name: str) -> str:\n        """Evita ejecutar hermes gateway status cada cinco segundos."""\n\n        # Comprueba si la caché sigue vigente y pertenece al mismo profile.\n        if (\n            self._gateway_checked_at is not None\n            and self._gateway_profile_name == profile_name\n            and now - self._gateway_checked_at < timedelta(seconds=_GATEWAY_CACHE_SECONDS)\n        ):\n            return self._gateway_status\n        # Ejecuta la sonda controlada para el profile seleccionado.\n        self._gateway_status = self._gateway_probe(profile_name)\n        # Guarda la fecha de actualización.\n        self._gateway_checked_at = now\n        # Asocia la caché con el profile consultado.\n        self._gateway_profile_name = profile_name\n        # Devuelve el estado observado.\n        return self._gateway_status\n''',
    "gateway cache",
)

method_marker = '''    # Construye una instantánea completa desde una conexión efímera.\n    def _collect_sync(self) -> PlatformSnapshot:\n'''
method_index = hermes.find(method_marker)
if method_index < 0:
    raise RuntimeError("No se encontró el método _collect_sync")

new_method = '''    # Inspecciona todas las bases válidas y selecciona el profile más reciente.\n    def _select_profile_source(\n        self,\n        sources: list[_HermesProfileSource],\n    ) -> tuple[_HermesProfileSource, _HermesSession | None] | None:\n        """Prioriza actividad real y usa active_profile únicamente como desempate."""\n\n        # Lee una sola vez el marcador oficial.\n        active_profile = _active_profile_name(self._hermes_root)\n        # Inicializa candidatos que pudieron abrirse correctamente.\n        candidates: list[tuple[_HermesProfileSource, _HermesSession | None]] = []\n        # Recorre cada base aislada sin mantener conexiones abiertas.\n        for source in sources:\n            try:\n                connection = _open_database(source.database_path)\n                try:\n                    session = _load_latest_session(connection)\n                finally:\n                    connection.close()\n            # Omite un profile dañado cuando otro profile sigue siendo legible.\n            except sqlite3.Error:\n                continue\n            # Conserva la fuente y su última sesión comprobada.\n            candidates.append((source, session))\n        # Indica que ninguna base pudo inspeccionarse.\n        if not candidates:\n            return None\n\n        # Construye una clave estable basada primero en actividad real.\n        def candidate_key(\n            candidate: tuple[_HermesProfileSource, _HermesSession | None],\n        ) -> tuple[float, int, int]:\n            # Separa la fuente de la sesión inspeccionada.\n            source, session = candidate\n            # Utiliza cero cuando el profile todavía no tiene sesiones.\n            activity = session.last_activity_at.timestamp() if session is not None else 0.0\n            # Utiliza el marcador oficial únicamente para resolver empates.\n            active_rank = int(active_profile == source.profile_name)\n            # Mantiene default como último desempate para compatibilidad.\n            default_rank = int(source.is_default)\n            # Devuelve la clave comparable.\n            return activity, active_rank, default_rank\n\n        # Devuelve el profile con actividad más nueva.\n        return max(candidates, key=candidate_key)\n\n    # Construye una instantánea completa desde una conexión efímera.\n    def _collect_sync(self) -> PlatformSnapshot:\n        """Descubre profiles, abre SQLite en modo ro y publica el más activo."""\n\n        # Descubre únicamente las ubicaciones oficiales de estado.\n        sources = _discover_profile_sources(self._hermes_root)\n        # Informa de ausencia cuando no existe ninguna base canónica.\n        if not sources:\n            return PlatformSnapshot(\n                platform_id=self.platform_id,\n                display_name="Hermes Agent",\n                status=AgentState.OFFLINE,\n                status_reason="state_db_unavailable",\n                status_message="No se encuentra state.db de Hermes ni de sus profiles.",\n            )\n        # Selecciona el profile con actividad real más reciente.\n        selected = self._select_profile_source(sources)\n        # Informa de error cuando existen bases pero ninguna es legible.\n        if selected is None:\n            return PlatformSnapshot(\n                platform_id=self.platform_id,\n                display_name="Hermes Agent",\n                status=AgentState.ERROR,\n                status_reason="state_db_error",\n                status_message="No se pudo leer ningún state.db de Hermes.",\n            )\n        # Separa la fuente seleccionada y la sesión ya inspeccionada.\n        source, inspected_session = selected\n        # Construye el nombre visible sin publicar la ruta local.\n        display_name = _profile_display_name(source)\n        # Obtiene la hora actual una sola vez para mantener coherencia.\n        now = datetime.now(UTC)\n        # Abre de nuevo solo la base seleccionada para completar su telemetría.\n        try:\n            connection = _open_database(source.database_path)\n            try:\n                # Relee la sesión para incluir cambios ocurridos durante el descubrimiento.\n                session = _load_latest_session(connection) or inspected_session\n                # Carga contadores exclusivos del profile seleccionado.\n                session_count, global_message_count = _load_global_counts(connection)\n                # Carga mensajes únicamente cuando hay una sesión.\n                messages = _load_messages(connection, session.session_id) if session else []\n            # Garantiza el cierre incluso cuando una consulta falle.\n            finally:\n                connection.close()\n        # Convierte errores del profile elegido en estado operativo visible.\n        except sqlite3.Error as error:\n            return PlatformSnapshot(\n                platform_id=self.platform_id,\n                display_name=display_name,\n                status=AgentState.ERROR,\n                status_reason="state_db_error",\n                status_message=_sanitize_text(str(error), 180) or "No se pudo leer state.db.",\n            )\n        # Representa una base válida pero sin sesiones.\n        if session is None:\n            return PlatformSnapshot(\n                platform_id=self.platform_id,\n                display_name=display_name,\n                status=AgentState.IDLE,\n                status_reason="no_sessions",\n                status_message=f"El profile {source.profile_name} no tiene sesiones registradas.",\n                runtime=PlatformRuntimeInfo(\n                    gateway_status=self._cached_gateway_status(now, source.profile_name),\n                    session_count=session_count,\n                    message_count=global_message_count,\n                    cron_job_count=_cron_job_count(source.home / "cron" / "jobs.json"),\n                ),\n            )\n        # Deriva estado y explicación desde datos reales.\n        status, status_reason, status_message = _derive_status(session, messages, now)\n        # Recupera la última solicitud visible.\n        latest_user = _latest_message(messages, {"user"})\n        # Recupera la última respuesta visible.\n        latest_assistant = _latest_message(messages, {"assistant"})\n        # Construye el alias de proyecto cuando cwd existe.\n        project_alias = _project_alias(session.cwd)\n        # Construye el proyecto opcional.\n        project = (\n            ProjectInfo(display_name=project_alias[0], cwd_alias=project_alias[1])\n            if project_alias is not None\n            else None\n        )\n        # Busca la ventana conocida dentro del profile seleccionado.\n        context_window = _context_window_from_cache(\n            source.home / "context_length_cache.yaml",\n            session.model,\n        )\n        # Construye el uso de tokens con referencia relativa al profile.\n        usage = _build_usage(\n            session,\n            context_window,\n            _profile_source_reference(source),\n        )\n        # Construye la tarea visible con título real de Hermes.\n        task = TaskInfo(\n            display_name=_optional_text(\n                session.title or (latest_user.content if latest_user is not None else None),\n                180,\n            ),\n            conversation_name=_optional_text(session.title, 120),\n            objective=_optional_text(\n                latest_user.content if latest_user is not None else None,\n                500,\n            ),\n            status=status,\n            activity=_optional_text(status_message, 180),\n            last_result=_optional_text(\n                latest_assistant.content if latest_assistant is not None else None,\n                220,\n            ),\n            started_at=session.started_at,\n            last_activity_at=session.last_activity_at,\n        )\n        # Identifica el originador y el profile sin publicar rutas.\n        originator_base = "Hermes Desktop" if session.source == "tui" else "Hermes Agent"\n        # Añade el profile únicamente cuando no es el predeterminado.\n        originator = (\n            originator_base\n            if source.is_default\n            else _optional_text(f"{originator_base} · {source.profile_name}", 80)\n        )\n        # Construye la instantánea final sin inventar cuotas o agentes.\n        return PlatformSnapshot(\n            platform_id=self.platform_id,\n            display_name=display_name,\n            status=status,\n            status_reason=status_reason,\n            status_message=status_message,\n            tokens_today=None,\n            cost_today=None,\n            active_agents=0,\n            agents=[],\n            token_usage=usage.thread_total,\n            usage=usage,\n            session=SessionInfo(\n                session_id=session.session_id,\n                started_at=session.started_at,\n                last_activity_at=session.last_activity_at,\n                originator=originator,\n                source=session.source,\n                model_provider=session.provider,\n                model_name=session.model,\n            ),\n            project=project,\n            task=task,\n            runtime=PlatformRuntimeInfo(\n                gateway_status=self._cached_gateway_status(now, source.profile_name),\n                session_count=session_count,\n                message_count=session.message_count,\n                tool_call_count=session.tool_call_count,\n                api_call_count=session.api_call_count,\n                cron_job_count=_cron_job_count(source.home / "cron" / "jobs.json"),\n                estimated_cost_usd=session.estimated_cost_usd,\n                actual_cost_usd=session.actual_cost_usd,\n                cost_status=session.cost_status,\n            ),\n            recent_activity=_build_activity(messages),\n        )\n'''

hermes = hermes[:method_index] + new_method
HERMES_PATH.write_text(hermes, encoding="utf-8")

tests = TEST_PATH.read_text(encoding="utf-8")
tests = tests.replace('gateway_probe=lambda: "stopped"', 'gateway_probe=lambda _profile: "stopped"')
tests = tests.replace('gateway_probe=lambda: "running"', 'gateway_probe=lambda _profile: "running"')

profile_test = r'''

# Valida el descubrimiento de un profile nombrado con actividad más reciente.
def test_discovers_most_recent_named_profile_without_mixing_state(tmp_path: Path) -> None:
    """Selecciona profiles/<nombre>/state.db y conserva aislamiento de sesiones."""

    # Crea la raíz equivalente a HERMES_HOME.
    hermes_root = tmp_path / "hermes"
    # Prepara la raíz del profile predeterminado.
    hermes_root.mkdir()
    # Crea la base del profile predeterminado con actividad antigua.
    default_connection = _create_database(hermes_root / "state.db")
    # Obtiene una referencia temporal común.
    now = time.time()
    # Inserta una sesión antigua que no debe seguir apareciendo.
    _insert_session(default_connection, now - 3600, title="Sesión antigua predeterminada")
    # Inserta una respuesta antigua para fijar la última actividad.
    default_connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "assistant",
            "Resultado antiguo.",
            now - 3500,
            "stop",
            1,
            0,
        ),
    )
    # Guarda y cierra la base predeterminada.
    default_connection.commit()
    default_connection.close()

    # Crea el contenedor oficial de profiles.
    profile_home = hermes_root / "profiles" / "genealogia"
    # Prepara la carpeta aislada del nuevo profile.
    profile_home.mkdir(parents=True)
    # Crea su base independiente.
    profile_connection = _create_database(profile_home / "state.db")
    # Inserta la sesión más reciente observada en Hermes Desktop.
    _insert_session(
        profile_connection,
        now - 20,
        title="Revisa HERMES.md y los archivos del árbol",
    )
    # Inserta una solicitud pendiente para representar trabajo en curso.
    profile_connection.execute(
        """
        INSERT INTO messages (
            session_id, role, content, timestamp, finish_reason, active, compacted
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "20260724_113225_5c7a60",
            "user",
            "Inicializa el registro de investigación sin modificar datos consolidados.",
            now,
            None,
            1,
            0,
        ),
    )
    # Guarda y cierra el profile nombrado.
    profile_connection.commit()
    profile_connection.close()
    # Registra el profile activo como desempate oficial.
    (hermes_root / "active_profile").write_text("genealogia\n", encoding="utf-8")

    # Registra el nombre recibido por la sonda de gateway.
    observed_profiles: list[str | None] = []

    # Ejecuta la captura sobre la raíz común.
    snapshot = asyncio.run(
        HermesAdapter(
            hermes_home=hermes_root,
            gateway_probe=lambda profile: observed_profiles.append(profile) or "running",
        ).collect()
    )

    # Confirma que el encabezado identifica el nuevo profile.
    assert snapshot.display_name == "Hermes · genealogia"
    # Confirma que se publica la conversación más reciente y no la antigua.
    assert snapshot.task is not None
    assert snapshot.task.conversation_name == "Revisa HERMES.md y los archivos del árbol"
    # Confirma el estado de trabajo derivado de la solicitud pendiente.
    assert snapshot.status == AgentState.WORKING
    # Confirma que la sonda consulta el mismo profile.
    assert observed_profiles == ["genealogia"]
    # Confirma la referencia relativa sin ruta del usuario.
    assert snapshot.token_usage is not None
    assert snapshot.token_usage.source_reference == "profiles/genealogia/state.db"
    # Impide filtrar el directorio temporal completo.
    assert str(tmp_path) not in snapshot.model_dump_json()
'''

if "test_discovers_most_recent_named_profile_without_mixing_state" in tests:
    raise RuntimeError("La prueba de profiles ya existe")
tests += profile_test
TEST_PATH.write_text(tests, encoding="utf-8")
