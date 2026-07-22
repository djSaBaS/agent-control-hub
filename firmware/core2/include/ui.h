#pragma once

// Importa la biblioteca unificada para pantalla y controles M5Stack.
#include <M5Unified.h>
// Importa tipos de texto utilizados por los datos recibidos.
#include <WString.h>

// Define las vistas principales disponibles en el dispositivo.
enum class ScreenId {
    // Muestra límites y resumen global.
    Dashboard,
    // Muestra agentes y estados individuales.
    Agents,
    // Muestra preferencias locales del dispositivo.
    Settings,
    // Muestra una alerta de consumo elevado.
    Warning,
};

// Agrupa los datos mínimos que utiliza el firmware en el MVP.
struct DeviceViewModel {
    // Guarda el porcentaje semanal restante o -1 cuando se desconoce.
    int weeklyRemaining = -1;
    // Guarda el porcentaje restante de la ventana corta o -1.
    int rollingRemaining = -1;
    // Guarda el nombre de la plataforma principal.
    String platformName = "Sin datos";
    // Guarda el texto de la próxima fecha de reinicio.
    String nextReset = "--";
    // Guarda el nombre de la tarea principal.
    String activeTask = "Sin actividad";
    // Guarda el número de agentes activos.
    int activeAgents = 0;
    // Guarda el coste total diario.
    float totalCostToday = 0.0F;
};

// Dibuja la vista seleccionada con los datos actuales.
void drawScreen(ScreenId screen, const DeviceViewModel& model);
