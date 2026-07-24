// Importa las declaraciones públicas de la interfaz.
#include "ui.h"

// Define el color de fondo común de la aplicación.
static constexpr uint32_t COLOR_BACKGROUND = 0x0D1117U;
// Define el color de las tarjetas de contenido.
static constexpr uint32_t COLOR_CARD = 0x161B22U;
// Define el color de una tarjeta seleccionada.
static constexpr uint32_t COLOR_SELECTED = 0x26364DU;
// Define el color principal de texto.
static constexpr uint32_t COLOR_TEXT = 0xF0F3F6U;
// Define el color secundario de texto.
static constexpr uint32_t COLOR_MUTED = 0x8B949EU;
// Define el color azul de información.
static constexpr uint32_t COLOR_BLUE = 0x58A6FFU;
// Define el color verde de estado correcto.
static constexpr uint32_t COLOR_GREEN = 0x3FB950U;
// Define el color amarillo de espera.
static constexpr uint32_t COLOR_YELLOW = 0xD29922U;
// Define el color rojo de error.
static constexpr uint32_t COLOR_RED = 0xF85149U;
// Define el color violeta de tarea activa.
static constexpr uint32_t COLOR_PURPLE = 0xA371F7U;
// Define el tiempo tras el que un snapshot se considera antiguo.
static constexpr uint32_t STALE_SNAPSHOT_MS = 15000U;

// Devuelve la plataforma seleccionada o un puntero nulo.
static const PlatformViewModel* selectedPlatform(const DeviceViewModel& model) {
    // Rechaza modelos sin plataformas válidas.
    if (model.platformCount == 0U) {
        // Informa de que no existe una plataforma seleccionable.
        return nullptr;
    }
    // Evita acceder fuera del límite cuando cambia el número de plataformas.
    if (model.selectedPlatformIndex >= model.platformCount) {
        // Utiliza la primera plataforma como alternativa segura.
        return &model.platforms[0];
    }
    // Devuelve la plataforma seleccionada por el usuario.
    return &model.platforms[model.selectedPlatformIndex];
}

// Devuelve una etiqueta breve para un estado operativo.
static const char* stateLabel(const PlatformState state) {
    // Selecciona la etiqueta correspondiente al estado recibido.
    switch (state) {
        // Etiqueta una plataforma disponible.
        case PlatformState::Idle:
            // Devuelve la etiqueta visible.
            return "DISPONIBLE";
        // Etiqueta una plataforma en ejecución.
        case PlatformState::Working:
            // Devuelve la etiqueta visible.
            return "TRABAJANDO";
        // Etiqueta una plataforma que espera una condición externa.
        case PlatformState::Waiting:
            // Devuelve la etiqueta visible.
            return "EN ESPERA";
        // Etiqueta una operación finalizada correctamente.
        case PlatformState::Completed:
            // Devuelve la etiqueta visible.
            return "COMPLETADO";
        // Etiqueta un fallo relevante.
        case PlatformState::Error:
            // Devuelve la etiqueta visible.
            return "ERROR";
        // Etiqueta una fuente no disponible.
        case PlatformState::Offline:
            // Devuelve la etiqueta visible.
            return "SIN CONEXION";
        // Etiqueta cualquier valor no reconocido.
        case PlatformState::Unknown:
            // Devuelve la etiqueta visible.
            return "DESCONOCIDO";
    }
    // Mantiene una salida segura ante valores futuros.
    return "DESCONOCIDO";
}

// Devuelve el color asociado a un estado operativo.
static uint32_t stateColor(const PlatformState state) {
    // Selecciona el color correspondiente al estado recibido.
    switch (state) {
        // Utiliza gris para una plataforma disponible.
        case PlatformState::Idle:
            // Devuelve el color secundario.
            return COLOR_MUTED;
        // Utiliza violeta para trabajo activo.
        case PlatformState::Working:
            // Devuelve el color de actividad.
            return COLOR_PURPLE;
        // Utiliza amarillo para una espera.
        case PlatformState::Waiting:
            // Devuelve el color de atención.
            return COLOR_YELLOW;
        // Utiliza verde para una operación completada.
        case PlatformState::Completed:
            // Devuelve el color de éxito.
            return COLOR_GREEN;
        // Utiliza rojo para errores.
        case PlatformState::Error:
            // Devuelve el color crítico.
            return COLOR_RED;
        // Utiliza rojo para una plataforma desconectada.
        case PlatformState::Offline:
            // Devuelve el color crítico.
            return COLOR_RED;
        // Utiliza azul para un estado desconocido.
        case PlatformState::Unknown:
            // Devuelve el color informativo.
            return COLOR_BLUE;
    }
    // Mantiene una salida segura ante valores futuros.
    return COLOR_BLUE;
}

// Selecciona un color según el porcentaje restante.
static uint32_t quotaColor(const int remaining) {
    // Utiliza gris cuando no existe un valor oficial.
    if (remaining < 0) {
        // Devuelve el color secundario para datos ausentes.
        return COLOR_MUTED;
    }
    // Utiliza rojo para cuotas críticas.
    if (remaining < 15) {
        // Devuelve el color de alerta crítica.
        return COLOR_RED;
    }
    // Utiliza amarillo para cuotas reducidas.
    if (remaining < 35) {
        // Devuelve el color de advertencia.
        return COLOR_YELLOW;
    }
    // Utiliza verde para cuotas suficientes.
    return COLOR_GREEN;
}

// Recorta un texto y añade puntos suspensivos cuando es necesario.
static String compactText(const String& value, const size_t maxLength) {
    // Devuelve directamente valores suficientemente cortos.
    if (value.length() <= maxLength) {
        // Conserva el texto completo.
        return value;
    }
    // Protege longitudes demasiado pequeñas para añadir el indicador.
    if (maxLength < 4U) {
        // Devuelve únicamente los caracteres disponibles.
        return value.substring(0, maxLength);
    }
    // Recorta el texto y añade tres puntos compatibles con la fuente integrada.
    return value.substring(0, maxLength - 3U) + "...";
}

// Dibuja un texto en varias líneas con un número máximo de caracteres.
static void drawWrappedText(
    const String& value,
    const int x,
    const int y,
    const size_t maxChars,
    const size_t maxLines,
    const uint32_t foreground,
    const uint32_t background
) {
    // Configura los colores del bloque.
    M5.Display.setTextColor(foreground, background);
    // Selecciona texto compacto para maximizar la información visible.
    M5.Display.setTextSize(1);
    // Inicializa la posición de lectura del texto.
    size_t offset = 0U;
    // Recorre el número máximo de líneas permitido.
    for (size_t lineIndex = 0U; lineIndex < maxLines && offset < value.length(); ++lineIndex) {
        // Calcula el final máximo de la línea actual.
        size_t end = offset + maxChars;
        // Limita el final a la longitud real del texto.
        if (end > value.length()) {
            // Utiliza el final real del texto.
            end = value.length();
        }
        // Busca un espacio para no cortar palabras cuando quedan caracteres posteriores.
        if (end < value.length()) {
            // Inicializa la posición de búsqueda desde el final calculado.
            size_t space = end;
            // Retrocede hasta encontrar un espacio o el inicio de la línea.
            while (space > offset && value.charAt(space) != ' ') {
                // Mueve la búsqueda un carácter hacia la izquierda.
                --space;
            }
            // Utiliza el espacio encontrado cuando mantiene una línea útil.
            if (space > offset + 4U) {
                // Ajusta el final al separador localizado.
                end = space;
            }
        }
        // Extrae la línea que se debe mostrar.
        String line = value.substring(offset, end);
        // Añade un indicador cuando se alcanza la última línea con texto pendiente.
        if (lineIndex + 1U == maxLines && end < value.length()) {
            // Recorta la última línea antes de añadir puntos suspensivos.
            line = compactText(line, maxChars);
        }
        // Posiciona el cursor en la línea actual.
        M5.Display.setCursor(x, y + static_cast<int>(lineIndex * 13U));
        // Escribe la línea preparada.
        M5.Display.print(line);
        // Avanza hasta el siguiente carácter no vacío.
        offset = end;
        // Omite espacios iniciales de la siguiente línea.
        while (offset < value.length() && value.charAt(offset) == ' ') {
            // Avanza un carácter adicional.
            ++offset;
        }
    }
}

// Dibuja el encabezado común de una pantalla.
static void drawHeader(const String& title, const DeviceViewModel& model) {
    // Configura el fondo de toda la pantalla.
    M5.Display.fillScreen(COLOR_BACKGROUND);
    // Selecciona el color de texto principal.
    M5.Display.setTextColor(COLOR_TEXT, COLOR_BACKGROUND);
    // Selecciona una fuente legible para el encabezado.
    M5.Display.setTextSize(2);
    // Posiciona el cursor con margen superior.
    M5.Display.setCursor(12, 10);
    // Escribe el título solicitado.
    M5.Display.print(compactText(title, 23U));
    // Calcula si la captura continúa vigente.
    const bool stale = !model.hasSnapshot || millis() - model.lastSnapshotAt > STALE_SNAPSHOT_MS;
    // Selecciona el color del indicador de conexión.
    const uint32_t connectionColor = stale ? COLOR_RED : COLOR_GREEN;
    // Dibuja el indicador en la esquina superior derecha.
    M5.Display.fillCircle(302, 17, 5, connectionColor);
}

// Dibuja la barra inferior común de navegación.
static void drawFooter(const char* left, const char* center, const char* right) {
    // Dibuja el fondo de navegación.
    M5.Display.fillRect(0, 211, 320, 29, COLOR_CARD);
    // Configura el estilo del pie.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Selecciona una fuente compacta.
    M5.Display.setTextSize(1);
    // Posiciona la acción izquierda.
    M5.Display.setCursor(12, 222);
    // Escribe la acción izquierda.
    M5.Display.print(left);
    // Centra la acción principal de forma aproximada.
    M5.Display.setCursor(126, 222);
    // Escribe la acción central.
    M5.Display.print(center);
    // Posiciona la acción derecha.
    M5.Display.setCursor(246, 222);
    // Escribe la acción derecha.
    M5.Display.print(right);
}

// Dibuja el resumen de todas las plataformas visibles.
static void drawDashboard(const DeviceViewModel& model) {
    // Dibuja el encabezado del producto.
    drawHeader("AGENT CONTROL HUB", model);
    // Muestra un estado vacío mientras no existe una captura válida.
    if (model.platformCount == 0U) {
        // Dibuja una tarjeta central vacía.
        M5.Display.fillRoundRect(12, 46, 296, 130, 8, COLOR_CARD);
        // Configura el texto principal.
        M5.Display.setTextColor(COLOR_TEXT, COLOR_CARD);
        // Selecciona texto mediano.
        M5.Display.setTextSize(2);
        // Posiciona el mensaje principal.
        M5.Display.setCursor(36, 82);
        // Informa de que se esperan datos serie.
        M5.Display.print("Esperando servicio");
        // Configura texto secundario.
        M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
        // Selecciona texto compacto.
        M5.Display.setTextSize(1);
        // Posiciona la velocidad del protocolo.
        M5.Display.setCursor(36, 119);
        // Informa de la velocidad de conexión.
        M5.Display.print("USB serie · 115200 baudios");
        // Dibuja el pie de navegación deshabilitado.
        drawFooter("A: --", "B: --", "C: --");
        // Finaliza la pantalla vacía.
        return;
    }
    // Recorre las plataformas visibles dentro del límite local.
    for (size_t index = 0U; index < model.platformCount; ++index) {
        // Recupera la plataforma de la fila actual.
        const PlatformViewModel& platform = model.platforms[index];
        // Calcula la posición vertical de la fila.
        const int y = 40 + static_cast<int>(index * 40U);
        // Detecta la plataforma seleccionada.
        const bool selected = index == model.selectedPlatformIndex;
        // Selecciona el color de fondo según la selección.
        const uint32_t rowBackground = selected ? COLOR_SELECTED : COLOR_CARD;
        // Dibuja la tarjeta compacta de plataforma.
        M5.Display.fillRoundRect(10, y, 300, 34, 7, rowBackground);
        // Dibuja el indicador de estado.
        M5.Display.fillCircle(23, y + 17, 5, stateColor(platform.status));
        // Configura el nombre visible.
        M5.Display.setTextColor(COLOR_TEXT, rowBackground);
        // Selecciona texto normal.
        M5.Display.setTextSize(1);
        // Posiciona el nombre de plataforma.
        M5.Display.setCursor(36, y + 7);
        // Escribe el nombre acotado.
        M5.Display.print(compactText(platform.displayName, 24U));
        // Configura el estado visible.
        M5.Display.setTextColor(stateColor(platform.status), rowBackground);
        // Posiciona el estado bajo el nombre.
        M5.Display.setCursor(36, y + 20);
        // Escribe la etiqueta de estado.
        M5.Display.print(stateLabel(platform.status));
        // Configura el proyecto como dato secundario.
        M5.Display.setTextColor(COLOR_MUTED, rowBackground);
        // Posiciona el proyecto a la derecha.
        M5.Display.setCursor(172, y + 13);
        // Escribe el proyecto acotado.
        M5.Display.print(compactText(platform.projectName, 20U));
    }
    // Dibuja el pie de navegación del resumen.
    drawFooter("A: Anterior", "B: Abrir", "C: Siguiente");
}

// Dibuja el detalle de la plataforma seleccionada.
static void drawPlatformDetail(const DeviceViewModel& model) {
    // Recupera la plataforma seleccionada de forma segura.
    const PlatformViewModel* platform = selectedPlatform(model);
    // Utiliza un título genérico cuando no existen datos.
    const String title = platform == nullptr ? "DETALLE" : platform->displayName;
    // Dibuja el encabezado de la plataforma.
    drawHeader(title, model);
    // Regresa al resumen visual cuando no existe plataforma.
    if (platform == nullptr) {
        // Dibuja el mensaje de ausencia.
        drawWrappedText("No hay plataformas visibles.", 18, 70, 40U, 2U, COLOR_MUTED, COLOR_BACKGROUND);
        // Dibuja el pie disponible.
        drawFooter("A: Resumen", "B: --", "C: --");
        // Finaliza la vista.
        return;
    }
    // Dibuja una tarjeta superior de estado y proyecto.
    M5.Display.fillRoundRect(10, 38, 300, 49, 7, COLOR_CARD);
    // Dibuja el indicador de estado.
    M5.Display.fillCircle(23, 54, 5, stateColor(platform->status));
    // Configura la etiqueta de estado.
    M5.Display.setTextColor(stateColor(platform->status), COLOR_CARD);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona la etiqueta.
    M5.Display.setCursor(36, 48);
    // Escribe el estado operativo.
    M5.Display.print(stateLabel(platform->status));
    // Configura el proyecto como dato secundario.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Posiciona el proyecto.
    M5.Display.setCursor(36, 65);
    // Escribe el proyecto o un marcador.
    M5.Display.print(compactText(platform->projectName.isEmpty() ? "Proyecto no disponible" : platform->projectName, 40U));
    // Dibuja la tarjeta de actividad principal.
    M5.Display.fillRoundRect(10, 94, 300, 65, 7, COLOR_CARD);
    // Configura la etiqueta de actividad.
    M5.Display.setTextColor(COLOR_BLUE, COLOR_CARD);
    // Posiciona la etiqueta.
    M5.Display.setCursor(20, 103);
    // Escribe la etiqueta.
    M5.Display.print("ACTIVIDAD");
    // Selecciona el texto más relevante disponible.
    String activity = platform->currentActivity;
    // Utiliza el último resultado cuando no existe actividad actual.
    if (activity.isEmpty()) {
        // Conserva el resultado como alternativa.
        activity = platform->lastResult;
    }
    // Utiliza el objetivo cuando tampoco existe resultado.
    if (activity.isEmpty()) {
        // Conserva el objetivo como última alternativa.
        activity = platform->objective;
    }
    // Utiliza el estado cuando no hay texto operativo.
    if (activity.isEmpty()) {
        // Conserva el mensaje de estado o su etiqueta.
        activity = platform->statusMessage.isEmpty() ? stateLabel(platform->status) : platform->statusMessage;
    }
    // Dibuja la actividad en un máximo de tres líneas.
    drawWrappedText(activity, 20, 119, 45U, 3U, COLOR_TEXT, COLOR_CARD);
    // Dibuja la tarjeta inferior de cuota y modelo.
    M5.Display.fillRoundRect(10, 166, 300, 38, 7, COLOR_CARD);
    // Configura el porcentaje principal.
    M5.Display.setTextColor(quotaColor(platform->rollingRemaining), COLOR_CARD);
    // Selecciona texto mediano.
    M5.Display.setTextSize(2);
    // Posiciona el porcentaje.
    M5.Display.setCursor(20, 176);
    // Escribe el porcentaje o marcador.
    if (platform->rollingRemaining >= 0) {
        // Publica el porcentaje oficial.
        M5.Display.printf("%d%%", platform->rollingRemaining);
    } else {
        // Publica un marcador de ausencia.
        M5.Display.print("--");
    }
    // Configura texto secundario para modelo y reinicio.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona el modelo.
    M5.Display.setCursor(83, 174);
    // Escribe el modelo activo.
    M5.Display.print(compactText(platform->modelName.isEmpty() ? "Modelo --" : platform->modelName, 31U));
    // Posiciona la fecha de reinicio.
    M5.Display.setCursor(83, 189);
    // Escribe la fecha oficial acotada.
    M5.Display.print(compactText(platform->nextReset.isEmpty() ? "Reinicio --" : platform->nextReset, 31U));
    // Dibuja el pie de navegación del detalle.
    drawFooter("A: Anterior", "B: Actividad", "C: Siguiente");
}

// Dibuja la actividad reciente de la plataforma seleccionada.
static void drawActivity(const DeviceViewModel& model) {
    // Recupera la plataforma seleccionada.
    const PlatformViewModel* platform = selectedPlatform(model);
    // Dibuja el encabezado de actividad.
    drawHeader("ACTIVIDAD RECIENTE", model);
    // Muestra una ausencia explícita cuando no existen eventos.
    if (platform == nullptr || platform->recentActivityCount == 0U) {
        // Dibuja una tarjeta vacía.
        M5.Display.fillRoundRect(10, 48, 300, 128, 7, COLOR_CARD);
        // Dibuja el mensaje centrado de forma aproximada.
        drawWrappedText("No hay actividad reciente disponible para esta plataforma.", 24, 80, 42U, 3U, COLOR_MUTED, COLOR_CARD);
        // Dibuja el pie de navegación.
        drawFooter("A: Anterior", "B: Sistema", "C: Siguiente");
        // Finaliza la vista vacía.
        return;
    }
    // Recorre las actividades disponibles.
    for (size_t index = 0U; index < platform->recentActivityCount; ++index) {
        // Recupera la actividad de la fila.
        const ActivityViewModel& activity = platform->recentActivity[index];
        // Calcula la posición vertical de la tarjeta.
        const int y = 40 + static_cast<int>(index * 54U);
        // Dibuja el fondo de la actividad.
        M5.Display.fillRoundRect(10, y, 300, 48, 7, COLOR_CARD);
        // Dibuja el indicador de estado.
        M5.Display.fillCircle(22, y + 15, 4, stateColor(activity.status));
        // Configura la etiqueta principal.
        M5.Display.setTextColor(COLOR_TEXT, COLOR_CARD);
        // Selecciona texto compacto.
        M5.Display.setTextSize(1);
        // Posiciona la etiqueta.
        M5.Display.setCursor(34, y + 8);
        // Escribe la etiqueta acotada.
        M5.Display.print(compactText(activity.label, 40U));
        // Dibuja el resumen en dos líneas.
        drawWrappedText(activity.summary, 34, y + 24, 42U, 2U, COLOR_MUTED, COLOR_CARD);
    }
    // Dibuja el pie de navegación de actividad.
    drawFooter("A: Anterior", "B: Sistema", "C: Siguiente");
}

// Dibuja diagnóstico de conexión y protocolo.
static void drawSystem(const DeviceViewModel& model) {
    // Dibuja el encabezado de sistema.
    drawHeader("SISTEMA", model);
    // Dibuja una tarjeta de diagnóstico.
    M5.Display.fillRoundRect(10, 44, 300, 154, 7, COLOR_CARD);
    // Calcula la antigüedad del último snapshot en segundos.
    const uint32_t ageSeconds = model.hasSnapshot ? (millis() - model.lastSnapshotAt) / 1000U : 0U;
    // Configura el texto principal.
    M5.Display.setTextColor(COLOR_TEXT, COLOR_CARD);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona el estado del enlace.
    M5.Display.setCursor(22, 58);
    // Escribe el estado del enlace.
    M5.Display.printf("Enlace USB: %s", model.hasSnapshot && ageSeconds < 15U ? "ACTIVO" : "SIN DATOS");
    // Posiciona la antigüedad.
    M5.Display.setCursor(22, 82);
    // Escribe la antigüedad disponible.
    M5.Display.printf("Ultimo snapshot: %lus", static_cast<unsigned long>(ageSeconds));
    // Posiciona el número de plataformas.
    M5.Display.setCursor(22, 106);
    // Escribe el número de plataformas visibles.
    M5.Display.printf("Plataformas: %u", static_cast<unsigned int>(model.platformCount));
    // Posiciona el coste agregado.
    M5.Display.setCursor(22, 130);
    // Escribe el coste diario conocido.
    M5.Display.printf("Coste hoy: %.2f", static_cast<double>(model.totalCostToday));
    // Configura el diagnóstico de protocolo.
    M5.Display.setTextColor(model.frameTooLarge ? COLOR_RED : COLOR_MUTED, COLOR_CARD);
    // Posiciona la etiqueta de protocolo.
    M5.Display.setCursor(22, 154);
    // Escribe el último diagnóstico acotado.
    M5.Display.print(compactText(model.protocolMessage, 43U));
    // Posiciona la versión del firmware.
    M5.Display.setCursor(22, 178);
    // Escribe la versión funcional del MVP.
    M5.Display.print("Firmware MVP multiplaforma · protocolo 1.0");
    // Dibuja el pie de navegación de sistema.
    drawFooter("A: Anterior", "B: Resumen", "C: Siguiente");
}

// Dibuja una alerta operativa retenida por el servicio.
static void drawAlert(const DeviceViewModel& model) {
    // Dibuja un fondo oscuro completo.
    M5.Display.fillScreen(COLOR_BACKGROUND);
    // Dibuja un borde verde para una restauración operativa.
    M5.Display.drawRoundRect(8, 8, 304, 196, 10, COLOR_GREEN);
    // Configura el título de alerta.
    M5.Display.setTextColor(COLOR_GREEN, COLOR_BACKGROUND);
    // Selecciona texto grande.
    M5.Display.setTextSize(2);
    // Posiciona el título.
    M5.Display.setCursor(20, 28);
    // Escribe el título acotado.
    M5.Display.print(compactText(model.alert.title, 24U));
    // Configura el identificador de plataforma.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_BACKGROUND);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona la plataforma.
    M5.Display.setCursor(20, 62);
    // Escribe la plataforma afectada.
    M5.Display.printf("Plataforma: %s", model.alert.platformId.c_str());
    // Dibuja el mensaje en varias líneas.
    drawWrappedText(model.alert.message, 20, 92, 44U, 5U, COLOR_TEXT, COLOR_BACKGROUND);
    // Dibuja el pie de confirmación.
    drawFooter("A: Cerrar", "B: Aceptar", "C: Cerrar");
}

// Selecciona y dibuja una pantalla completa.
void drawScreen(const ScreenId screen, const DeviceViewModel& model) {
    // Fuerza la alerta mientras exista un evento activo.
    if (model.alert.active || screen == ScreenId::Alert) {
        // Renderiza la alerta emergente.
        drawAlert(model);
        // Evita dibujar la vista subyacente.
        return;
    }
    // Selecciona la implementación según la pantalla solicitada.
    switch (screen) {
        // Dibuja el resumen de plataformas.
        case ScreenId::Dashboard:
            // Renderiza el resumen multiplaforma.
            drawDashboard(model);
            // Finaliza este caso.
            break;
        // Dibuja el detalle de una plataforma.
        case ScreenId::PlatformDetail:
            // Renderiza proyecto, actividad y cuota.
            drawPlatformDetail(model);
            // Finaliza este caso.
            break;
        // Dibuja la actividad reciente.
        case ScreenId::Activity:
            // Renderiza los eventos técnicos recientes.
            drawActivity(model);
            // Finaliza este caso.
            break;
        // Dibuja el diagnóstico local.
        case ScreenId::System:
            // Renderiza conexión y protocolo.
            drawSystem(model);
            // Finaliza este caso.
            break;
        // Mantiene una salida defensiva para una alerta sin datos.
        case ScreenId::Alert:
            // Renderiza la alerta actual.
            drawAlert(model);
            // Finaliza este caso.
            break;
    }
}

// Reproduce una señal breve cuando aparece una alerta nueva.
void playAlertSignal() {
    // Ajusta un volumen moderado para no resultar intrusivo.
    M5.Speaker.setVolume(80U);
    // Reproduce un primer tono de confirmación.
    M5.Speaker.tone(1568U, 110U);
    // Separa brevemente ambos tonos.
    delay(130U);
    // Reproduce un segundo tono ascendente.
    M5.Speaker.tone(2093U, 140U);
}
