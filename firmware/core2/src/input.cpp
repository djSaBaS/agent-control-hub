// Importa la biblioteca unificada para leer botones y pantalla táctil.
#include <M5Unified.h>
// Importa el contrato de entrada independiente del hardware.
#include "input.h"

// Convierte una pulsación táctil inferior en una acción de navegación.
static NavigationAction readTouchNavigation() {
    // Recupera el último detalle táctil normalizado por M5Unified.
    const auto touch = M5.Touch.getDetail();
    // Ignora estados que no representan una nueva pulsación.
    if (!touch.wasPressed()) {
        // Informa de que no existe una acción nueva.
        return NavigationAction::None;
    }
    // Reserva la franja inferior de la pantalla para navegación común.
    const int navigationTop = M5.Display.height() - 48;
    // Ignora pulsaciones realizadas fuera de la franja de navegación.
    if (touch.y < navigationTop) {
        // Informa de que la pantalla actual debe mantenerse.
        return NavigationAction::None;
    }
    // Divide la anchura visible en tres zonas equivalentes.
    const int sectionWidth = M5.Display.width() / 3;
    // Asigna la zona izquierda al resumen global.
    if (touch.x < sectionWidth) {
        // Solicita mostrar el resumen.
        return NavigationAction::ShowDashboard;
    }
    // Asigna la zona central a la actividad de agentes.
    if (touch.x < sectionWidth * 2) {
        // Solicita mostrar la lista de agentes.
        return NavigationAction::ShowAgents;
    }
    // Asigna la zona derecha a la configuración local.
    return NavigationAction::ShowSettings;
}

// Inicializa la capa de entrada específica del dispositivo.
void initializeInput() {
    // M5Unified inicializa botones y tacto durante M5.begin().
}

// Obtiene una única acción de navegación normalizada.
NavigationAction readNavigationAction() {
#if defined(AGENT_CONTROL_BOARD_CORE2)
    // Conserva el acceso directo mediante la zona capacitiva A del Core2.
    if (M5.BtnA.wasPressed()) {
        // Solicita mostrar el resumen global.
        return NavigationAction::ShowDashboard;
    }
    // Conserva el acceso directo mediante la zona capacitiva B del Core2.
    if (M5.BtnB.wasPressed()) {
        // Solicita mostrar la actividad de agentes.
        return NavigationAction::ShowAgents;
    }
    // Conserva el acceso directo mediante la zona capacitiva C del Core2.
    if (M5.BtnC.wasPressed()) {
        // Solicita mostrar la configuración.
        return NavigationAction::ShowSettings;
    }
#endif
    // Utiliza navegación táctil común en Core2 y en la familia CoreS3.
    return readTouchNavigation();
}
