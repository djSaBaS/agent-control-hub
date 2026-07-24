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
    const int navigationTop = M5.Display.height() - 42;
    // Ignora pulsaciones realizadas fuera de la franja de navegación.
    if (touch.y < navigationTop) {
        // Informa de que la pantalla actual debe mantenerse.
        return NavigationAction::None;
    }
    // Divide la anchura visible en tres zonas equivalentes.
    const int sectionWidth = M5.Display.width() / 3;
    // Asigna la zona izquierda a la acción anterior.
    if (touch.x < sectionWidth) {
        // Solicita retroceder o mover la selección a la izquierda.
        return NavigationAction::Previous;
    }
    // Asigna la zona central a la confirmación.
    if (touch.x < sectionWidth * 2) {
        // Solicita abrir la vista o aceptar la alerta actual.
        return NavigationAction::Select;
    }
    // Asigna la zona derecha a la acción siguiente.
    return NavigationAction::Next;
}

// Inicializa la capa de entrada específica del dispositivo.
void initializeInput() {
    // M5Unified inicializa botones y tacto durante M5.begin().
}

// Obtiene una única acción de navegación normalizada.
NavigationAction readNavigationAction() {
#if defined(AGENT_CONTROL_BOARD_CORE2)
    // Conserva el botón A como acción anterior en Core2.
    if (M5.BtnA.wasPressed()) {
        // Solicita retroceder o seleccionar la plataforma anterior.
        return NavigationAction::Previous;
    }
    // Conserva el botón B como acción de selección en Core2.
    if (M5.BtnB.wasPressed()) {
        // Solicita abrir o confirmar el elemento actual.
        return NavigationAction::Select;
    }
    // Conserva el botón C como acción siguiente en Core2.
    if (M5.BtnC.wasPressed()) {
        // Solicita avanzar o seleccionar la plataforma siguiente.
        return NavigationAction::Next;
    }
#endif
    // Utiliza navegación táctil común en Core2 y en la familia CoreS3.
    return readTouchNavigation();
}
