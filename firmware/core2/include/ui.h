#pragma once

// Importa la biblioteca unificada para pantalla y periféricos M5Stack.
#include <M5Unified.h>
// Importa tipos de texto utilizados por los datos normalizados.
#include <WString.h>

// Limita el número de plataformas almacenadas en el microcontrolador.
static constexpr size_t MAX_DEVICE_PLATFORMS = 4U;
// Limita la actividad reciente almacenada por plataforma.
static constexpr size_t MAX_DEVICE_ACTIVITIES = 3U;

// Define los estados operativos que puede recibir el protocolo.
enum class PlatformState {
    // Indica que la plataforma está disponible sin trabajo activo.
    Idle,
    // Indica que existe trabajo o una herramienta en ejecución.
    Working,
    // Indica que la plataforma espera una condición externa.
    Waiting,
    // Indica que la última operación terminó correctamente.
    Completed,
    // Indica que la última operación terminó con un error relevante.
    Error,
    // Indica que la fuente local no está disponible.
    Offline,
    // Indica que el protocolo recibió un estado desconocido.
    Unknown,
};

// Define las vistas principales del firmware físico.
enum class ScreenId {
    // Muestra todas las plataformas visibles y su estado.
    Dashboard,
    // Muestra proyecto, conversación, actividad y cuota de una plataforma.
    PlatformDetail,
    // Muestra la actividad técnica reciente de la plataforma seleccionada.
    Activity,
    // Muestra conexión, antigüedad y diagnóstico local.
    System,
    // Muestra una alerta operativa que interrumpe temporalmente la navegación.
    Alert,
};

// Agrupa una actividad técnica reciente ya sanitizada por el servicio.
struct ActivityViewModel {
    // Guarda la etiqueta breve del evento.
    String label;
    // Guarda un resumen acotado del evento.
    String summary;
    // Guarda el estado asociado al evento.
    PlatformState status = PlatformState::Unknown;
};

// Agrupa la información visual de una plataforma normalizada.
struct PlatformViewModel {
    // Guarda el identificador estable de la plataforma.
    String platformId;
    // Guarda el nombre visible de la plataforma.
    String displayName = "Sin datos";
    // Guarda el estado operativo actual.
    PlatformState status = PlatformState::Unknown;
    // Guarda una explicación breve del estado.
    String statusMessage;
    // Guarda el nombre sanitizado del proyecto.
    String projectName;
    // Guarda el título fiable de la conversación.
    String conversationName;
    // Guarda el objetivo o tarea visible.
    String objective;
    // Guarda la actividad que se está realizando ahora.
    String currentActivity;
    // Guarda el último resultado técnico relevante.
    String lastResult;
    // Guarda el nombre del modelo activo cuando existe.
    String modelName;
    // Guarda la próxima fecha oficial de reinicio.
    String nextReset;
    // Guarda el porcentaje restante de la primera ventana o -1.
    int rollingRemaining = -1;
    // Guarda el porcentaje restante de la segunda ventana o -1.
    int weeklyRemaining = -1;
    // Guarda el número de agentes secundarios confirmados.
    int activeAgents = 0;
    // Guarda hasta tres actividades recientes.
    ActivityViewModel recentActivity[MAX_DEVICE_ACTIVITIES];
    // Guarda cuántas actividades recientes son válidas.
    size_t recentActivityCount = 0U;
};

// Agrupa una alerta retenida por el servicio local.
struct AlertViewModel {
    // Indica si existe una alerta visible actualmente.
    bool active = false;
    // Guarda el identificador utilizado para evitar duplicados.
    String alertId;
    // Guarda el identificador de la plataforma afectada.
    String platformId;
    // Guarda el título de la alerta.
    String title;
    // Guarda el mensaje descriptivo de la alerta.
    String message;
    // Guarda el instante local en el que debe desaparecer.
    uint32_t expiresAt = 0U;
};

// Agrupa el estado completo que utiliza la interfaz del dispositivo.
struct DeviceViewModel {
    // Guarda las plataformas visibles recibidas en el último snapshot.
    PlatformViewModel platforms[MAX_DEVICE_PLATFORMS];
    // Guarda el número de plataformas válidas.
    size_t platformCount = 0U;
    // Guarda el índice de la plataforma seleccionada.
    size_t selectedPlatformIndex = 0U;
    // Guarda el coste total diario agregado cuando existe.
    float totalCostToday = 0.0F;
    // Guarda el instante local del último snapshot válido.
    uint32_t lastSnapshotAt = 0U;
    // Indica si se ha recibido al menos un snapshot válido.
    bool hasSnapshot = false;
    // Indica si el último frame superó el tamaño permitido.
    bool frameTooLarge = false;
    // Guarda el último diagnóstico breve del protocolo.
    String protocolMessage = "Esperando datos";
    // Guarda la alerta emergente actual.
    AlertViewModel alert;
    // Guarda el último identificador mostrado para evitar repeticiones.
    String lastDisplayedAlertId;
};

// Dibuja la vista seleccionada con el estado completo del dispositivo.
void drawScreen(ScreenId screen, const DeviceViewModel& model);

// Reproduce una señal breve cuando aparece una alerta nueva.
void playAlertSignal();
