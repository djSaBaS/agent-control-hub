"""Aplica correcciones deterministas de navegación y protocolo al firmware MVP."""

# Importa Path para limitar las modificaciones a archivos conocidos.
from pathlib import Path


# Sustituye una aparición exacta y detiene la ejecución ante divergencias.
def replace_once(path: Path, old: str, new: str) -> None:
    """Evita aplicar una migración parcial sobre una revisión inesperada."""

    # Lee el archivo completo con codificación estable.
    content = path.read_text(encoding="utf-8")
    # Cuenta las apariciones del ancla esperada.
    occurrences = content.count(old)
    # Rechaza anclas ausentes o ambiguas.
    if occurrences != 1:
        # Explica qué archivo no coincide con la revisión esperada.
        raise RuntimeError(f"Ancla no única en {path}: {occurrences}")
    # Sustituye exclusivamente la aparición validada.
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


# Resuelve la raíz del repositorio desde la ubicación del script.
root = Path(__file__).resolve().parents[1]
# Resuelve el receptor principal del firmware.
main_path = root / "firmware/core2/src/main.cpp"
# Resuelve el renderizador de interfaz.
ui_path = root / "firmware/core2/src/ui.cpp"

# Protege el acceso al segundo carácter de la versión del protocolo.
replace_once(
    # Modifica únicamente el receptor serie.
    main_path,
    # Localiza la validación que asume dos caracteres.
    "    if (protocolVersion[0] != '1' || protocolVersion[1] != '.') {\n",
    # Comprueba primero la longitud declarada.
    "    if (std::strlen(protocolVersion) < 2U || protocolVersion[0] != '1' || protocolVersion[1] != '.') {\n",
)

# Corrige el pie de la vista Detalle para reflejar selección circular.
replace_once(
    # Modifica únicamente la interfaz.
    ui_path,
    # Localiza el pie anterior de Detalle.
    '    drawFooter("A: Resumen", "B: Actividad", "C: Siguiente");\n',
    # Publica la acción real del botón A.
    '    drawFooter("A: Anterior", "B: Actividad", "C: Siguiente");\n',
)

# Corrige el pie de la vista Actividad para reflejar el ciclo de pantallas.
replace_once(
    # Modifica únicamente la interfaz.
    ui_path,
    # Localiza el pie anterior de Actividad.
    '    drawFooter("A: Detalle", "B: Resumen", "C: Siguiente");\n',
    # Publica la navegación real de la acción central.
    '    drawFooter("A: Anterior", "B: Sistema", "C: Siguiente");\n',
)

# Corrige el pie de la vista Sistema para reflejar selección y regreso.
replace_once(
    # Modifica únicamente la interfaz.
    ui_path,
    # Localiza el pie anterior de Sistema.
    '    drawFooter("A: Resumen", "B: Detalle", "C: Resumen");\n',
    # Publica las acciones reales de los tres controles.
    '    drawFooter("A: Anterior", "B: Resumen", "C: Siguiente");\n',
)
