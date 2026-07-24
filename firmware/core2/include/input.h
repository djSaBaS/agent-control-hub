#pragma once

// Define las acciones de navegación independientes del hardware.
enum class NavigationAction {
    // Indica que no se ha producido ninguna acción.
    None,
    // Solicita mover la selección o regresar a la vista anterior.
    Previous,
    // Solicita abrir la vista seleccionada o confirmar una acción.
    Select,
    // Solicita mover la selección o avanzar a la vista siguiente.
    Next,
};

// Inicializa la capa de entrada específica del dispositivo.
void initializeInput();

// Obtiene una única acción de navegación normalizada.
NavigationAction readNavigationAction();
