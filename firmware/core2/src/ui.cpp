// Importa las declaraciones públicas de la interfaz.
#include "ui.h"

// Define el color de fondo común de la aplicación.
static constexpr uint32_t COLOR_BACKGROUND = 0x101214U;
// Define el color de las tarjetas de contenido.
static constexpr uint32_t COLOR_CARD = 0x20252BU;
// Define el color principal de texto.
static constexpr uint32_t COLOR_TEXT = 0xF1F3F5U;
// Define el color secundario de texto.
static constexpr uint32_t COLOR_MUTED = 0xA4ADB7U;
// Define el color azul de información.
static constexpr uint32_t COLOR_BLUE = 0x4C9AFFU;
// Define el color verde de estado correcto.
static constexpr uint32_t COLOR_GREEN = 0x55D66BU;
// Define el color amarillo de advertencia.
static constexpr uint32_t COLOR_YELLOW = 0xFFC857U;
// Define el color rojo de alerta crítica.
static constexpr uint32_t COLOR_RED = 0xFF5C47U;

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

// Dibuja el encabezado común de una pantalla.
static void drawHeader(const String& title) {
    // Configura el fondo de toda la pantalla.
    M5.Display.fillScreen(COLOR_BACKGROUND);
    // Selecciona el color de texto principal.
    M5.Display.setTextColor(COLOR_TEXT, COLOR_BACKGROUND);
    // Selecciona una fuente legible para el encabezado.
    M5.Display.setTextSize(2);
    // Posiciona el cursor con margen superior.
    M5.Display.setCursor(14, 12);
    // Escribe el título solicitado.
    M5.Display.print(title);
}

// Dibuja una barra horizontal de porcentaje.
static void drawProgressBar(const int x, const int y, const int width, const int value) {
    // Limita el valor al rango representable.
    const int safeValue = constrain(value, 0, 100);
    // Dibuja el fondo de la barra.
    M5.Display.fillRoundRect(x, y, width, 10, 4, 0x303840U);
    // Calcula la anchura proporcional del valor.
    const int filledWidth = (width * safeValue) / 100;
    // Dibuja la parte rellena cuando tiene anchura visible.
    if (filledWidth > 0) {
        // Utiliza el color de cuota correspondiente.
        M5.Display.fillRoundRect(x, y, filledWidth, 10, 4, quotaColor(value));
    }
}

// Dibuja el resumen principal de límites.
static void drawDashboard(const DeviceViewModel& model) {
    // Dibuja el encabezado de producto.
    drawHeader("AGENT CONTROL");
    // Dibuja la tarjeta semanal.
    M5.Display.fillRoundRect(12, 42, 296, 70, 8, COLOR_CARD);
    // Configura el estilo de la etiqueta.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona la etiqueta semanal.
    M5.Display.setCursor(24, 53);
    // Escribe la etiqueta semanal.
    M5.Display.print("SEMANA");
    // Configura el color dinámico del porcentaje.
    M5.Display.setTextColor(quotaColor(model.weeklyRemaining), COLOR_CARD);
    // Selecciona texto grande para el porcentaje.
    M5.Display.setTextSize(3);
    // Posiciona el porcentaje semanal.
    M5.Display.setCursor(24, 67);
    // Muestra un marcador cuando el valor no está disponible.
    if (model.weeklyRemaining < 0) {
        // Escribe el marcador de dato desconocido.
        M5.Display.print("--");
    } else {
        // Escribe el porcentaje semanal.
        M5.Display.printf("%d%%", model.weeklyRemaining);
    }
    // Dibuja la barra semanal.
    drawProgressBar(130, 76, 160, model.weeklyRemaining);
    // Configura el estilo del reinicio.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Reduce el texto del reinicio.
    M5.Display.setTextSize(1);
    // Posiciona la fecha de reinicio.
    M5.Display.setCursor(130, 93);
    // Escribe la fecha recibida o su marcador.
    M5.Display.print(model.nextReset);
    // Dibuja la tarjeta de ventana corta.
    M5.Display.fillRoundRect(12, 120, 296, 62, 8, COLOR_CARD);
    // Configura la etiqueta de ventana corta.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Posiciona la etiqueta.
    M5.Display.setCursor(24, 132);
    // Escribe la etiqueta de cinco horas.
    M5.Display.print("VENTANA CORTA");
    // Configura el color del porcentaje corto.
    M5.Display.setTextColor(quotaColor(model.rollingRemaining), COLOR_CARD);
    // Selecciona texto grande.
    M5.Display.setTextSize(3);
    // Posiciona el porcentaje corto.
    M5.Display.setCursor(24, 147);
    // Muestra un marcador cuando el valor no está disponible.
    if (model.rollingRemaining < 0) {
        // Escribe el marcador de dato desconocido.
        M5.Display.print("--");
    } else {
        // Escribe el porcentaje de la ventana corta.
        M5.Display.printf("%d%%", model.rollingRemaining);
    }
    // Dibuja la barra de ventana corta.
    drawProgressBar(130, 153, 160, model.rollingRemaining);
    // Configura el estilo del pie de pantalla.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_BACKGROUND);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona el resumen de agentes.
    M5.Display.setCursor(14, 198);
    // Escribe plataforma y agentes activos.
    M5.Display.printf("%s  |  Agentes activos: %d", model.platformName.c_str(), model.activeAgents);
    // Posiciona la ayuda de navegación.
    M5.Display.setCursor(14, 222);
    // Escribe las acciones de los tres controles.
    M5.Display.print("A: Resumen   B: Agentes   C: Config");
}

// Dibuja una lista compacta de actividad.
static void drawAgents(const DeviceViewModel& model) {
    // Dibuja el encabezado de agentes.
    drawHeader("AGENTES");
    // Dibuja una tarjeta de actividad principal.
    M5.Display.fillRoundRect(12, 44, 296, 105, 8, COLOR_CARD);
    // Dibuja el punto de estado activo.
    M5.Display.fillCircle(28, 66, 6, COLOR_BLUE);
    // Configura el nombre de la plataforma.
    M5.Display.setTextColor(COLOR_TEXT, COLOR_CARD);
    // Selecciona texto normal.
    M5.Display.setTextSize(2);
    // Posiciona el nombre de la plataforma.
    M5.Display.setCursor(44, 58);
    // Escribe el nombre de la plataforma.
    M5.Display.print(model.platformName);
    // Configura el nombre de la tarea.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona el nombre de la tarea.
    M5.Display.setCursor(24, 88);
    // Escribe la tarea activa truncada por la pantalla.
    M5.Display.print(model.activeTask.substring(0, 35));
    // Posiciona el número de agentes.
    M5.Display.setCursor(24, 113);
    // Escribe el número de agentes activos.
    M5.Display.printf("Activos: %d", model.activeAgents);
    // Posiciona el coste diario.
    M5.Display.setCursor(24, 132);
    // Escribe el coste diario agregado.
    M5.Display.printf("Coste hoy: %.2f", static_cast<double>(model.totalCostToday));
    // Dibuja la ayuda inferior.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_BACKGROUND);
    // Posiciona la ayuda de navegación.
    M5.Display.setCursor(14, 222);
    // Escribe las acciones de navegación.
    M5.Display.print("A: Resumen   B: Actualizar   C: Config");
}

// Dibuja opciones locales todavía no persistidas.
static void drawSettings() {
    // Dibuja el encabezado de configuración.
    drawHeader("CONFIGURACION");
    // Dibuja la tarjeta de opciones.
    M5.Display.fillRoundRect(12, 44, 296, 142, 8, COLOR_CARD);
    // Configura el color de texto principal.
    M5.Display.setTextColor(COLOR_TEXT, COLOR_CARD);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona la primera opción.
    M5.Display.setCursor(24, 60);
    // Escribe la opción de brillo.
    M5.Display.print("Brillo");
    // Posiciona el estado del brillo.
    M5.Display.setCursor(250, 60);
    // Escribe el valor actual de brillo.
    M5.Display.print("80%");
    // Posiciona la segunda opción.
    M5.Display.setCursor(24, 88);
    // Escribe la opción de vibración.
    M5.Display.print("Vibracion");
    // Posiciona el estado de vibración.
    M5.Display.setCursor(250, 88);
    // Escribe el valor actual de vibración.
    M5.Display.print("ON");
    // Posiciona la tercera opción.
    M5.Display.setCursor(24, 116);
    // Escribe el umbral de aviso.
    M5.Display.print("Alerta semanal");
    // Posiciona el valor del umbral.
    M5.Display.setCursor(250, 116);
    // Escribe el umbral inicial.
    M5.Display.print("30%");
    // Posiciona la cuarta opción.
    M5.Display.setCursor(24, 144);
    // Escribe el modo de color.
    M5.Display.print("Tema");
    // Posiciona el valor del tema.
    M5.Display.setCursor(250, 144);
    // Escribe el tema oscuro.
    M5.Display.print("OSCURO");
    // Configura el texto de información.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_CARD);
    // Posiciona el estado de persistencia.
    M5.Display.setCursor(24, 168);
    // Informa de la limitación actual del MVP.
    M5.Display.print("Persistencia NVS pendiente");
    // Dibuja la ayuda inferior.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_BACKGROUND);
    // Posiciona la ayuda de navegación.
    M5.Display.setCursor(14, 222);
    // Escribe las acciones de navegación.
    M5.Display.print("A: Resumen   B: Agentes   C: Config");
}

// Dibuja una alerta crítica de consumo semanal.
static void drawWarning(const DeviceViewModel& model) {
    // Dibuja el encabezado de alerta.
    drawHeader("CONSUMO ELEVADO");
    // Dibuja la tarjeta de alerta.
    M5.Display.fillRoundRect(12, 44, 296, 145, 8, 0x351817U);
    // Configura el color principal de alerta.
    M5.Display.setTextColor(COLOR_RED, 0x351817U);
    // Selecciona texto grande.
    M5.Display.setTextSize(3);
    // Posiciona el porcentaje semanal.
    M5.Display.setCursor(24, 61);
    // Escribe el porcentaje restante.
    M5.Display.printf("%d%%", max(model.weeklyRemaining, 0));
    // Configura el texto descriptivo.
    M5.Display.setTextColor(COLOR_TEXT, 0x351817U);
    // Selecciona texto compacto.
    M5.Display.setTextSize(1);
    // Posiciona el nombre de la tarea.
    M5.Display.setCursor(24, 105);
    // Escribe la tarea que coincide con la alerta.
    M5.Display.printf("Objetivo: %s", model.activeTask.substring(0, 31).c_str());
    // Posiciona la descripción de riesgo.
    M5.Display.setCursor(24, 129);
    // Escribe una advertencia prudente.
    M5.Display.print("La cuota semanal esta por debajo del limite.");
    // Dibuja la barra de cuota crítica.
    drawProgressBar(24, 154, 264, model.weeklyRemaining);
    // Configura el texto de ayuda.
    M5.Display.setTextColor(COLOR_MUTED, COLOR_BACKGROUND);
    // Posiciona la ayuda inferior.
    M5.Display.setCursor(14, 222);
    // Informa de cómo regresar al resumen.
    M5.Display.print("Pulsa A para volver al resumen");
}

// Selecciona y dibuja una pantalla completa.
void drawScreen(const ScreenId screen, const DeviceViewModel& model) {
    // Selecciona la implementación según la pantalla solicitada.
    switch (screen) {
        // Dibuja la pantalla principal.
        case ScreenId::Dashboard:
            // Renderiza el resumen de límites.
            drawDashboard(model);
            // Finaliza este caso.
            break;
        // Dibuja la pantalla de agentes.
        case ScreenId::Agents:
            // Renderiza la actividad disponible.
            drawAgents(model);
            // Finaliza este caso.
            break;
        // Dibuja la pantalla de configuración.
        case ScreenId::Settings:
            // Renderiza las preferencias locales.
            drawSettings();
            // Finaliza este caso.
            break;
        // Dibuja la pantalla de alerta.
        case ScreenId::Warning:
            // Renderiza el aviso crítico.
            drawWarning(model);
            // Finaliza este caso.
            break;
    }
}
