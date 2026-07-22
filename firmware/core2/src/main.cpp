// Importa la biblioteca de JSON utilizada para el protocolo.
#include <ArduinoJson.h>
// Importa la biblioteca unificada del hardware M5Stack.
#include <M5Unified.h>
// Importa la capa de entrada independiente del dispositivo.
#include "input.h"
// Importa las funciones y modelos de la interfaz.
#include "ui.h"

// Guarda el modelo mostrado actualmente.
static DeviceViewModel viewModel;
// Guarda la pantalla activa del dispositivo.
static ScreenId currentScreen = ScreenId::Dashboard;
// Guarda el mensaje serie recibido hasta el salto de línea.
static String serialBuffer;
// Guarda el instante de la última instantánea válida.
static uint32_t lastSnapshotAt = 0U;

// Convierte una fecha ISO a un texto corto para la pantalla.
static String compactResetText(const char* value) {
    // Devuelve un marcador cuando no existe fecha.
    if (value == nullptr || value[0] == '\0') {
        // Informa de que el reinicio no está disponible.
        return "Reinicio: --";
    }
    // Convierte la entrada recibida en un objeto String.
    const String isoValue(value);
    // Conserva una longitud segura para la pantalla.
    return String("Reinicio: ") + isoValue.substring(0, min(16, static_cast<int>(isoValue.length())));
}

// Actualiza el modelo de vista a partir de un documento JSON validado.
static bool applySnapshot(const JsonDocument& document) {
    // Verifica que el mensaje corresponda al tipo esperado.
    if (document["type"] != "snapshot") {
        // Rechaza mensajes desconocidos sin modificar la pantalla.
        return false;
    }
    // Recupera la colección de plataformas del mensaje.
    const JsonArrayConst platforms = document["platforms"].as<JsonArrayConst>();
    // Rechaza instantáneas sin plataformas utilizables.
    if (platforms.isNull() || platforms.size() == 0U) {
        // Informa de que no se aplicaron datos.
        return false;
    }
    // Selecciona la primera plataforma para el MVP.
    const JsonObjectConst platform = platforms[0].as<JsonObjectConst>();
    // Actualiza el nombre visible de la plataforma.
    viewModel.platformName = platform["display_name"] | "Sin datos";
    // Actualiza el porcentaje semanal o conserva -1.
    viewModel.weeklyRemaining = platform["weekly_remaining_pct"] | -1;
    // Actualiza el porcentaje de la ventana corta o conserva -1.
    viewModel.rollingRemaining = platform["rolling_remaining_pct"] | -1;
    // Actualiza el número de agentes activos.
    viewModel.activeAgents = platform["active_agents"] | 0;
    // Actualiza el texto del próximo reinicio.
    viewModel.nextReset = compactResetText(platform["next_reset_at"] | nullptr);
    // Actualiza el coste total diario del mensaje.
    viewModel.totalCostToday = document["total_cost_today"] | 0.0F;
    // Recupera la lista de agentes de la plataforma.
    const JsonArrayConst agents = platform["agents"].as<JsonArrayConst>();
    // Utiliza el primer agente como tarea principal cuando exista.
    if (!agents.isNull() && agents.size() > 0U) {
        // Recupera el primer agente recibido.
        const JsonObjectConst firstAgent = agents[0].as<JsonObjectConst>();
        // Utiliza el nombre de tarea o el nombre del agente como alternativa.
        viewModel.activeTask = firstAgent["task_name"] | firstAgent["display_name"] | "Sin actividad";
    } else {
        // Restablece el texto cuando no hay agentes disponibles.
        viewModel.activeTask = "Sin actividad";
    }
    // Registra el instante de recepción válida.
    lastSnapshotAt = millis();
    // Selecciona la alerta cuando la cuota semanal está en estado crítico.
    if (viewModel.weeklyRemaining >= 0 && viewModel.weeklyRemaining < 15) {
        // Cambia automáticamente a la vista de alerta.
        currentScreen = ScreenId::Warning;
    }
    // Redibuja la pantalla con el modelo actualizado.
    drawScreen(currentScreen, viewModel);
    // Informa de que el mensaje fue aplicado correctamente.
    return true;
}

// Procesa una línea completa recibida por el puerto serie.
static void processSerialLine(const String& line) {
    // Ignora líneas vacías para evitar errores de análisis.
    if (line.isEmpty()) {
        // Finaliza sin modificar el estado.
        return;
    }
    // Reserva memoria dinámica suficiente para el mensaje MVP.
    JsonDocument document;
    // Analiza el JSON recibido desde Windows.
    const DeserializationError error = deserializeJson(document, line);
    // Informa por serie cuando el mensaje no es JSON válido.
    if (error) {
        // Escribe un prefijo de error legible.
        Serial.print("JSON_ERROR: ");
        // Escribe el detalle proporcionado por ArduinoJson.
        Serial.println(error.c_str());
        // Finaliza sin actualizar la pantalla.
        return;
    }
    // Aplica la instantánea normalizada al modelo local.
    const bool applied = applySnapshot(document);
    // Informa del resultado para diagnóstico.
    Serial.println(applied ? "SNAPSHOT_OK" : "SNAPSHOT_IGNORED");
}

// Lee bytes serie y forma mensajes delimitados por salto de línea.
static void readSerialMessages() {
    // Procesa todos los bytes disponibles sin bloquear el bucle.
    while (Serial.available() > 0) {
        // Lee el siguiente carácter del puerto serie.
        const char character = static_cast<char>(Serial.read());
        // Procesa la línea completa cuando llega el delimitador.
        if (character == '\n') {
            // Envía el búfer completo al analizador.
            processSerialLine(serialBuffer);
            // Limpia el búfer para el siguiente mensaje.
            serialBuffer = "";
            // Continúa con posibles bytes adicionales.
            continue;
        }
        // Evita acumular retornos de carro utilizados por algunos terminales.
        if (character == '\r') {
            // Ignora el carácter de retorno.
            continue;
        }
        // Añade el carácter al mensaje actual.
        serialBuffer += character;
        // Protege la memoria ante mensajes malformados demasiado grandes.
        if (serialBuffer.length() > 8192U) {
            // Descarta el mensaje incompleto excedido.
            serialBuffer = "";
            // Informa del descarte por seguridad.
            Serial.println("FRAME_TOO_LARGE");
        }
    }
}

// Aplica una acción de navegación normalizada a la interfaz.
static void handleNavigation() {
    // Obtiene una única acción desde botones, tacto o futuros controles externos.
    const NavigationAction action = readNavigationAction();
    // Selecciona la respuesta correspondiente a la acción recibida.
    switch (action) {
        // Mantiene la pantalla cuando no existe una acción nueva.
        case NavigationAction::None:
            // Finaliza sin redibujar para evitar trabajo innecesario.
            return;
        // Abre el resumen global.
        case NavigationAction::ShowDashboard:
            // Selecciona la pantalla principal.
            currentScreen = ScreenId::Dashboard;
            // Finaliza la selección de la acción.
            break;
        // Abre la actividad de agentes.
        case NavigationAction::ShowAgents:
            // Selecciona la pantalla de agentes.
            currentScreen = ScreenId::Agents;
            // Finaliza la selección de la acción.
            break;
        // Abre la configuración local.
        case NavigationAction::ShowSettings:
            // Selecciona la pantalla de configuración.
            currentScreen = ScreenId::Settings;
            // Finaliza la selección de la acción.
            break;
    }
    // Redibuja la pantalla seleccionada con el último modelo disponible.
    drawScreen(currentScreen, viewModel);
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
    delay(200);
    // Configura la rotación horizontal natural de la pantalla.
    M5.Display.setRotation(1);
    // Configura un brillo inicial moderado.
    M5.Display.setBrightness(180);
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
    // Cede tiempo al sistema para evitar un bucle agresivo.
    delay(10);
}
