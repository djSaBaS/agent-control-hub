#pragma once

// Define las acciones de navegación independientes del hardware.
enum class NavigationAction {
    // Indica que no se ha producido ninguna acción.
    None,
    // Solicita mostrar la pantalla principal.
    ShowDashboard,
    // Solicita mostrar la pantalla de agentes.
    ShowAgents,
    // Solicita mostrar la pantalla de configuración.
    ShowSettings,
};

// Inicializa la capa de entrada específica del dispositivo.
void initializeInput();

// Obtiene una única acción de navegación normalizada.
NavigationAction readNavigationAction();
