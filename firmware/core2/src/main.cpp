// Importa la biblioteca de JSON utilizada para el protocolo.
#include <ArduinoJson.h>
// Importa la biblioteca unificada del hardware M5Stack.
#include <M5Unified.h>
// Importa funciones de comparación de texto C.
#include <cstring>
// Importa la capa de entrada independiente del dispositivo.
#include "input.h"
// Importa las funciones y modelos de la interfaz.
#include "ui.h"

// Limita cada frame NDJSON para proteger la memoria del microcontrolador.
static constexpr size_t MAX_SERIAL_FRAME_SIZE = 65536U;
// Define el tiempo visible de una alerta emergente.
static constexpr uint32_t ALERT_VISIBLE_MS = 15000U;
// Define el intervalo de refresco del indicador de conexión.
static constexpr uint32_t STATUS_REFRESH_MS = 1000U;

// Guarda el modelo mostrado actualmente.
static DeviceViewModel viewModel;
// Guarda la pantalla activa del dispositivo.
static ScreenId currentScreen = ScreenId::Dashboard;
// Guarda la pantalla que debe restaurarse después de una alerta.
static ScreenId screenBeforeAlert = ScreenId::Dashboard;
// Reserva un búfer fijo para una línea NDJSON completa.
static char serialBuffer[MAX_SERIAL_FRAME_SIZE + 1U];
// Guarda el número de bytes válidos del frame actual.
static size_t serialLength = 0U;
// Indica que se está descartando un frame que superó el límite.
static bool discardingOversizedFrame = false;
// Guarda el último instante de refresco periódico.
static uint32_t lastStatusRefreshAt = 0U;

// Recorta un texto recibido para limitar asignaciones dinámicas.
static String boundedText(
    const JsonVariantConst value,
    const char* fallback,
    const size_t maxLength
) {
    // Recupera un puntero seguro desde el documento JSON.
    const char* rawValue = value | fallback;
    // Convierte el valor recibido en un texto Arduino.
    String result = rawValue == nullptr ? String() : String(rawValue);
    // Devuelve directamente valores dentro del límite.
    if (result.length() <= maxLength) {
        // Conserva el texto completo.
        return result;
    }
    // Protege límites demasiado pequeños para un indicador de recorte.
    if (maxLength < 4U) {
        // Devuelve únicamente el número permitido de caracteres.
        return result.substring(0, maxLength);
    }
    // Recorta el valor y añade puntos suspensivos compatibles con la fuente.
    return result.substring(0, maxLength - 3U) + "...";
}

// Convierte un estado textual del protocolo al modelo local.
static PlatformState parsePlatformState(const char* value) {
    // Rechaza punteros nulos como estados desconocidos.
    if (value == nullptr) {
        // Devuelve el estado defensivo.
        return PlatformState::Unknown;
    }
    // Detecta el estado disponible.
    if (std::strcmp(value, "idle") == 0) {
        // Devuelve el estado local equivalente.
        return PlatformState::Idle;
    }
    // Detecta el estado de trabajo.
    if (std::strcmp(value, "working") == 0) {
        // Devuelve el estado local equivalente.
        return PlatformState::Working;
    }
    // Detecta el estado de espera.
    if (std::strcmp(value, "waiting") == 0) {
        // Devuelve el estado local equivalente.
        return PlatformState::Waiting;
    }
    // Detecta el estado completado.
    if (std::strcmp(value, "completed") == 0) {
        // Devuelve el estado local equivalente.
        return PlatformState::Completed;
    }
    // Detecta el estado de error.
    if (std::strcmp(value, "error") == 0) {
        // Devuelve el estado local equivalente.
        return PlatformState::Error;
    }
    // Detecta una fuente desconectada.
    if (std::strcmp(value, "offline") == 0) {
        // Devuelve el estado local equivalente.
        return PlatformState::Offline;
    }
    // Mantiene un valor defensivo para estados futuros.
    return PlatformState::Unknown;
}

// Convierte una fecha ISO en un texto compacto para 320 píxeles.
static String compactResetText(const JsonVariantConst value) {
    // Recupera el valor de fecha sin inventar un reinicio.
    const String isoValue = boundedText(value, "", 32U);
    // Devuelve un marcador cuando la fecha no está disponible.
    if (isoValue.isEmpty()) {
        // Informa de que no existe una fecha oficial.
        return "Reinicio --";
    }
    // Conserva mes, día y hora cuando llega el formato ISO esperado.
    if (isoValue.length() >= 16U) {
        // Construye una fecha compacta sin zona ni segundos.
        return String("Reinicio ") + isoValue.substring(5, 16);
    }
    // Devuelve el valor corto recibido cuando no sigue el formato esperado.
    return String("Reinicio ") + isoValue;
}

// Limpia una plataforma antes de reutilizar su posición fija.
static void resetPlatform(PlatformViewModel& platform) {
    // Sustituye todos los campos por sus valores iniciales.
    platform = PlatformViewModel{};
}

// Analiza una plataforma normalizada dentro de un espacio fijo.
static void parsePlatform(
    const JsonObjectConst platformObject,
    PlatformViewModel& platform
) {
    // Limpia posibles datos de una captura anterior.
    resetPlatform(platform);
    // Recupera el identificador estable.
    platform.platformId = boundedText(platformObject["platform_id"], "unknown", 24U);
    // Recupera el nombre visible.
    platform.displayName = boundedText(platformObject["display_name"], "Sin datos", 32U);
    // Convierte el estado recibido.
    platform.status = parsePlatformState(platformObject["status"] | nullptr);
    // Recupera el mensaje de estado ya sanitizado.
    platform.statusMessage = boundedText(platformObject["status_message"], "", 96U);
    // Recupera la primera cuota restante compatible.
    platform.rollingRemaining = platformObject["rolling_remaining_pct"] | -1;
    // Recupera la cuota semanal cuando existe.
    platform.weeklyRemaining = platformObject["weekly_remaining_pct"] | -1;
    // Recupera el número de agentes secundarios confirmados.
    platform.activeAgents = platformObject["active_agents"] | 0;
    // Recupera la fecha oficial de reinicio.
    platform.nextReset = compactResetText(platformObject["next_reset_at"]);

    // Recupera el proyecto opcional.
    const JsonObjectConst project = platformObject["project"].as<JsonObjectConst>();
    // Comprueba que el proyecto exista antes de leerlo.
    if (!project.isNull()) {
        // Conserva el nombre sanitizado del proyecto.
        platform.projectName = boundedText(project["display_name"], "", 48U);
    }

    // Recupera los metadatos opcionales de sesión.
    const JsonObjectConst session = platformObject["session"].as<JsonObjectConst>();
    // Comprueba que la sesión exista antes de leerla.
    if (!session.isNull()) {
        // Conserva el modelo activo cuando la fuente lo publica.
        platform.modelName = boundedText(session["model_name"], "", 40U);
    }

    // Recupera la tarea normalizada opcional.
    const JsonObjectConst task = platformObject["task"].as<JsonObjectConst>();
    // Comprueba que la tarea exista antes de leerla.
    if (!task.isNull()) {
        // Conserva el título fiable de conversación.
        platform.conversationName = boundedText(task["conversation_name"], "", 64U);
        // Conserva el objetivo visible o el nombre derivado.
        platform.objective = boundedText(task["objective"], "", 96U);
        // Utiliza el nombre visible cuando no existe un objetivo separado.
        if (platform.objective.isEmpty()) {
            // Conserva la tarea derivada como alternativa.
            platform.objective = boundedText(task["display_name"], "", 96U);
        }
        // Conserva la actividad actual.
        platform.currentActivity = boundedText(task["activity"], "", 96U);
        // Conserva el último resultado técnico.
        platform.lastResult = boundedText(task["last_result"], "", 96U);
    }

    // Recupera la actividad técnica reciente.
    const JsonArrayConst activities = platformObject["recent_activity"].as<JsonArrayConst>();
    // Recorre solo los primeros eventos permitidos por el modelo fijo.
    for (const JsonVariantConst activityValue : activities) {
        // Detiene el análisis al alcanzar el límite local.
        if (platform.recentActivityCount >= MAX_DEVICE_ACTIVITIES) {
            // Evita almacenar eventos adicionales.
            break;
        }
        // Interpreta el evento como objeto.
        const JsonObjectConst activityObject = activityValue.as<JsonObjectConst>();
        // Omite entradas no estructuradas.
        if (activityObject.isNull()) {
            // Continúa con la siguiente entrada.
            continue;
        }
        // Recupera la posición fija disponible.
        ActivityViewModel& activity = platform.recentActivity[platform.recentActivityCount];
        // Conserva la etiqueta breve.
        activity.label = boundedText(activityObject["label"], "Actividad", 48U);
        // Conserva el resumen acotado.
        activity.summary = boundedText(activityObject["summary"], "", 96U);
        // Convierte el estado del evento.
        activity.status = parsePlatformState(activityObject["status"] | nullptr);
        // Incrementa el número de eventos válidos.
        ++platform.recentActivityCount;
    }
}

// Activa la primera alerta nueva que no se haya mostrado anteriormente.
static bool applyNewAlert(const JsonArrayConst alerts) {
    // Omite el análisis cuando el snapshot no contiene alertas.
    if (alerts.isNull()) {
        // Informa de que no se aplicó ninguna alerta.
        return false;
    }
    // Recorre las alertas retenidas por el servicio.
    for (const JsonVariantConst alertValue : alerts) {
        // Interpreta la alerta como objeto JSON.
        const JsonObjectConst alertObject = alertValue.as<JsonObjectConst>();
        // Omite entradas no estructuradas.
        if (alertObject.isNull()) {
            // Continúa con la siguiente alerta.
            continue;
        }
        // Recupera el identificador deduplicable.
        const String alertId = boundedText(alertObject["alert_id"], "", 120U);
        // Omite alertas sin identificador o ya mostradas.
        if (alertId.isEmpty() || alertId == viewModel.lastDisplayedAlertId) {
            // Continúa buscando una alerta nueva.
            continue;
        }
        // Conserva la pantalla que se debe restaurar después del aviso.
        screenBeforeAlert = currentScreen == ScreenId::Alert ? ScreenId::Dashboard : currentScreen;
        // Marca la alerta como activa.
        viewModel.alert.active = true;
        // Conserva el identificador del evento.
        viewModel.alert.alertId = alertId;
        // Conserva la plataforma afectada.
        viewModel.alert.platformId = boundedText(alertObject["platform_id"], "", 24U);
        // Conserva el título visible.
        viewModel.alert.title = boundedText(alertObject["title"], "Alerta", 96U);
        // Conserva la explicación visible.
        viewModel.alert.message = boundedText(alertObject["message"], "", 160U);
        // Calcula el final del tiempo de visualización.
        viewModel.alert.expiresAt = millis() + ALERT_VISIBLE_MS;
        // Registra el identificador para evitar repeticiones durante la retención.
        viewModel.lastDisplayedAlertId = alertId;
        // Cambia a la vista emergente.
        currentScreen = ScreenId::Alert;
        // Reproduce una señal breve de aviso.
        playAlertSignal();
        // Informa de que se aplicó una alerta nueva.
        return true;
    }
    // Informa de que no había eventos nuevos.
    return false;
}

// Actualiza el modelo de vista a partir de un documento JSON validado.
static bool applySnapshot(const JsonDocument& document) {
    // Verifica que el mensaje corresponda al tipo esperado.
    if (document["type"] != "snapshot") {
        // Rechaza mensajes desconocidos sin modificar plataformas.
        return false;
    }
    // Recupera la versión declarada del protocolo.
    const char* protocolVersion = document["protocol_version"] | "";
    // Acepta únicamente versiones compatibles con la rama 1.x.
    if (std::strlen(protocolVersion) < 2U || protocolVersion[0] != '1' || protocolVersion[1] != '.') {
        // Publica un diagnóstico no sensible.
        viewModel.protocolMessage = "Version de protocolo no compatible";
        // Rechaza el snapshot recibido.
        return false;
    }
    // Recupera la colección de plataformas del mensaje.
    const JsonArrayConst platforms = document["platforms"].as<JsonArrayConst>();
    // Rechaza instantáneas sin plataformas utilizables.
    if (platforms.isNull() || platforms.size() == 0U) {
        // Publica un diagnóstico breve.
        viewModel.protocolMessage = "Snapshot sin plataformas";
        // Informa de que no se aplicaron datos.
        return false;
    }
    // Limpia las posiciones de plataformas de la captura anterior.
    for (size_t index = 0U; index < MAX_DEVICE_PLATFORMS; ++index) {
        // Restablece cada posición fija.
        resetPlatform(viewModel.platforms[index]);
    }
    // Restablece el contador antes de analizar la nueva captura.
    viewModel.platformCount = 0U;
    // Recorre las plataformas hasta alcanzar el límite local.
    for (const JsonVariantConst platformValue : platforms) {
        // Detiene el análisis cuando se ha llenado el modelo fijo.
        if (viewModel.platformCount >= MAX_DEVICE_PLATFORMS) {
            // Evita procesar plataformas adicionales.
            break;
        }
        // Interpreta la plataforma como objeto.
        const JsonObjectConst platformObject = platformValue.as<JsonObjectConst>();
        // Omite entradas no estructuradas.
        if (platformObject.isNull()) {
            // Continúa con la siguiente plataforma.
            continue;
        }
        // Analiza la plataforma dentro de la posición disponible.
        parsePlatform(platformObject, viewModel.platforms[viewModel.platformCount]);
        // Incrementa el número de plataformas válidas.
        ++viewModel.platformCount;
    }
    // Rechaza una captura que no contenía objetos de plataforma válidos.
    if (viewModel.platformCount == 0U) {
        // Publica el diagnóstico correspondiente.
        viewModel.protocolMessage = "Plataformas no validas";
        // Informa de que la captura no puede utilizarse.
        return false;
    }
    // Ajusta la selección cuando desaparece una plataforma.
    if (viewModel.selectedPlatformIndex >= viewModel.platformCount) {
        // Selecciona la primera plataforma disponible.
        viewModel.selectedPlatformIndex = 0U;
    }
    // Actualiza el coste total diario agregado.
    viewModel.totalCostToday = document["total_cost_today"] | 0.0F;
    // Registra el instante de recepción válida.
    viewModel.lastSnapshotAt = millis();
    // Marca que ya existe una captura utilizable.
    viewModel.hasSnapshot = true;
    // Limpia un error de tamaño anterior después de una captura correcta.
    viewModel.frameTooLarge = false;
    // Publica un diagnóstico positivo.
    viewModel.protocolMessage = "Snapshot recibido correctamente";
    // Aplica alertas nuevas después de actualizar las plataformas.
    applyNewAlert(document["alerts"].as<JsonArrayConst>());
    // Redibuja la pantalla con el modelo actualizado.
    drawScreen(currentScreen, viewModel);
    // Informa de que el mensaje fue aplicado correctamente.
    return true;
}

// Procesa el frame completo acumulado en el búfer fijo.
static void processSerialFrame() {
    // Ignora frames vacíos para evitar análisis innecesarios.
    if (serialLength == 0U) {
        // Finaliza sin modificar el estado.
        return;
    }
    // Añade el terminador requerido por las operaciones de texto.
    serialBuffer[serialLength] = '\0';
    // Reserva un documento dinámico gestionado por ArduinoJson.
    JsonDocument document;
    // Analiza exactamente el número de bytes recibidos.
    const DeserializationError error = deserializeJson(document, serialBuffer, serialLength);
    // Informa por serie cuando el mensaje no es JSON válido.
    if (error) {
        // Publica un diagnóstico breve en el modelo.
        viewModel.protocolMessage = String("JSON: ") + error.c_str();
        // Escribe un prefijo de error legible.
        Serial.print("JSON_ERROR: ");
        // Escribe el detalle proporcionado por ArduinoJson.
        Serial.println(error.c_str());
        // Redibuja el diagnóstico si se está mostrando Sistema.
        if (currentScreen == ScreenId::System) {
            // Actualiza la pantalla visible.
            drawScreen(currentScreen, viewModel);
        }
        // Finaliza sin sustituir el último snapshot válido.
        return;
    }
    // Aplica la instantánea normalizada al modelo local.
    const bool applied = applySnapshot(document);
    // Informa del resultado para diagnóstico del puerto serie.
    Serial.println(applied ? "SNAPSHOT_OK" : "SNAPSHOT_IGNORED");
}

// Lee bytes serie y forma mensajes delimitados por salto de línea.
static void readSerialMessages() {
    // Procesa todos los bytes disponibles sin bloquear el bucle.
    while (Serial.available() > 0) {
        // Lee el siguiente carácter del puerto serie.
        const char character = static_cast<char>(Serial.read());
        // Procesa el final del frame cuando llega un salto de línea.
        if (character == '\n') {
            // Procesa el frame solo cuando no se estaba descartando.
            if (!discardingOversizedFrame) {
                // Envía el búfer completo al analizador.
                processSerialFrame();
            }
            // Restablece la longitud para el siguiente frame.
            serialLength = 0U;
            // Permite recibir de nuevo después del delimitador.
            discardingOversizedFrame = false;
            // Continúa con posibles bytes adicionales.
            continue;
        }
        // Evita acumular retornos de carro utilizados por algunos terminales.
        if (character == '\r') {
            // Ignora el carácter de retorno.
            continue;
        }
        // Descarta todos los bytes hasta el siguiente salto tras un exceso.
        if (discardingOversizedFrame) {
            // Continúa sin escribir fuera del búfer.
            continue;
        }
        // Detecta el límite antes de almacenar el siguiente byte.
        if (serialLength >= MAX_SERIAL_FRAME_SIZE) {
            // Activa el descarte hasta el final de la línea.
            discardingOversizedFrame = true;
            // Restablece la longitud del frame inválido.
            serialLength = 0U;
            // Marca el diagnóstico visible.
            viewModel.frameTooLarge = true;
            // Publica una explicación breve.
            viewModel.protocolMessage = "Frame superior a 64 KB descartado";
            // Informa del descarte por seguridad.
            Serial.println("FRAME_TOO_LARGE");
            // Continúa con los bytes restantes del frame inválido.
            continue;
        }
        // Añade el carácter en la siguiente posición disponible.
        serialBuffer[serialLength] = character;
        // Incrementa la longitud válida.
        ++serialLength;
    }
}

// Selecciona la plataforma anterior con recorrido circular.
static void selectPreviousPlatform() {
    // Evita operaciones cuando no existen plataformas.
    if (viewModel.platformCount == 0U) {
        // Mantiene la selección actual.
        return;
    }
    // Salta a la última plataforma desde la primera.
    if (viewModel.selectedPlatformIndex == 0U) {
        // Selecciona la última posición válida.
        viewModel.selectedPlatformIndex = viewModel.platformCount - 1U;
        // Finaliza el cambio.
        return;
    }
    // Retrocede una posición.
    --viewModel.selectedPlatformIndex;
}

// Selecciona la plataforma siguiente con recorrido circular.
static void selectNextPlatform() {
    // Evita operaciones cuando no existen plataformas.
    if (viewModel.platformCount == 0U) {
        // Mantiene la selección actual.
        return;
    }
    // Avanza y vuelve al inicio al superar el límite.
    viewModel.selectedPlatformIndex =
        (viewModel.selectedPlatformIndex + 1U) % viewModel.platformCount;
}

// Cierra la alerta actual y restaura la pantalla anterior.
static void dismissAlert() {
    // Marca que la alerta ya no debe interrumpir la interfaz.
    viewModel.alert.active = false;
    // Restaura la pantalla que estaba visible.
    currentScreen = screenBeforeAlert;
    // Redibuja inmediatamente la vista restaurada.
    drawScreen(currentScreen, viewModel);
}

// Aplica una acción de navegación normalizada a la interfaz.
static void handleNavigation() {
    // Obtiene una única acción desde botones, tacto o futuros controles externos.
    const NavigationAction action = readNavigationAction();
    // Mantiene la pantalla cuando no existe una acción nueva.
    if (action == NavigationAction::None) {
        // Finaliza sin redibujar para evitar trabajo innecesario.
        return;
    }
    // Cierra cualquier alerta mediante una acción explícita del usuario.
    if (viewModel.alert.active) {
        // Descarta el aviso actual.
        dismissAlert();
        // Evita aplicar la misma pulsación a la vista restaurada.
        return;
    }
    // Mueve la selección a la plataforma anterior.
    if (action == NavigationAction::Previous) {
        // Actualiza la selección circular.
        selectPreviousPlatform();
        // Redibuja la pantalla con la nueva plataforma.
        drawScreen(currentScreen, viewModel);
        // Finaliza el tratamiento de la acción.
        return;
    }
    // Mueve la selección a la plataforma siguiente.
    if (action == NavigationAction::Next) {
        // Actualiza la selección circular.
        selectNextPlatform();
        // Redibuja la pantalla con la nueva plataforma.
        drawScreen(currentScreen, viewModel);
        // Finaliza el tratamiento de la acción.
        return;
    }
    // Avanza por las vistas mediante la acción central.
    switch (currentScreen) {
        // Abre el detalle desde el resumen.
        case ScreenId::Dashboard:
            // Selecciona la vista de plataforma.
            currentScreen = ScreenId::PlatformDetail;
            // Finaliza este caso.
            break;
        // Abre la actividad desde el detalle.
        case ScreenId::PlatformDetail:
            // Selecciona la vista de actividad.
            currentScreen = ScreenId::Activity;
            // Finaliza este caso.
            break;
        // Abre el diagnóstico desde la actividad.
        case ScreenId::Activity:
            // Selecciona la vista de sistema.
            currentScreen = ScreenId::System;
            // Finaliza este caso.
            break;
        // Regresa al resumen desde el diagnóstico.
        case ScreenId::System:
            // Selecciona el resumen multiplaforma.
            currentScreen = ScreenId::Dashboard;
            // Finaliza este caso.
            break;
        // Restaura el resumen ante una alerta residual.
        case ScreenId::Alert:
            // Selecciona la pantalla principal.
            currentScreen = ScreenId::Dashboard;
            // Finaliza este caso.
            break;
    }
    // Redibuja la pantalla seleccionada con el último modelo disponible.
    drawScreen(currentScreen, viewModel);
}

// Cierra automáticamente una alerta cuyo tiempo visible ha finalizado.
static void updateAlertTimeout() {
    // Finaliza cuando no existe una alerta activa.
    if (!viewModel.alert.active) {
        // Evita cálculos innecesarios.
        return;
    }
    // Compara tiempos de forma segura ante el desbordamiento de millis().
    const int32_t remaining = static_cast<int32_t>(viewModel.alert.expiresAt - millis());
    // Mantiene la alerta mientras no haya llegado su vencimiento.
    if (remaining > 0) {
        // Finaliza sin modificar la interfaz.
        return;
    }
    // Cierra el aviso y restaura la pantalla anterior.
    dismissAlert();
}

// Refresca periódicamente el indicador de conexión y antigüedad.
static void refreshStatusIfRequired() {
    // Obtiene el instante actual del sistema.
    const uint32_t now = millis();
    // Mantiene la pantalla cuando no ha transcurrido el intervalo.
    if (now - lastStatusRefreshAt < STATUS_REFRESH_MS) {
        // Finaliza sin redibujar.
        return;
    }
    // Guarda el instante del refresco realizado.
    lastStatusRefreshAt = now;
    // Redibuja únicamente las vistas cuyo estado depende del tiempo.
    if (currentScreen == ScreenId::Dashboard || currentScreen == ScreenId::System) {
        // Actualiza el indicador de conexión o la antigüedad.
        drawScreen(currentScreen, viewModel);
    }
}

// Inicializa hardware, comunicación e interfaz.
void setup() {
    // Obtiene una configuración base compatible con M5Unified.
    auto config = M5.config();
    // Activa la alimentación de periféricos necesaria para el dispositivo.
    config.output_power = true;
    // Inicializa el hardware unificado.
    M5.begin(config);
    // Inicializa la capa portátil de entrada.
    initializeInput();
    // Inicia el puerto serie con la velocidad del protocolo.
    Serial.begin(115200);
    // Espera brevemente a que el puerto serie esté disponible.
    delay(200U);
    // Configura la rotación horizontal natural de la pantalla.
    M5.Display.setRotation(1);
    // Configura un brillo inicial moderado.
    M5.Display.setBrightness(180U);
    // Evita divisiones automáticas de línea inesperadas.
    M5.Display.setTextWrap(false);
    // Dibuja la pantalla inicial sin datos.
    drawScreen(currentScreen, viewModel);
    // Informa de que el firmware está preparado.
    Serial.println("AGENT_CONTROL_READY");
}

// Ejecuta el ciclo de entrada, comunicación y actualización.
void loop() {
    // Actualiza el estado de controles táctiles y hardware.
    M5.update();
    // Lee y procesa mensajes serie disponibles.
    readSerialMessages();
    // Atiende la navegación solicitada por el usuario.
    handleNavigation();
    // Gestiona el cierre automático de alertas.
    updateAlertTimeout();
    // Refresca estados dependientes del tiempo.
    refreshStatusIfRequired();
    // Cede tiempo al sistema para evitar un bucle agresivo.
    delay(10U);
}
