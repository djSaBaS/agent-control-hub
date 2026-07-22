# Integración continua

## Flujos disponibles

### CI · Servicio Python

Ejecuta:

1. Instalación y comprobación de dependencias.
2. Compilación de sintaxis con `compileall`.
3. Reglas de calidad con Ruff.
4. Validación de formato con Ruff Format.
5. Tipado estricto con MyPy.
6. Pruebas con Pytest.
7. Cobertura de líneas y ramas.
8. Construcción y validación del paquete Python.

Las pruebas se ejecutan en Python 3.11, 3.12 y 3.13.

### CI · Firmware M5Stack

Compila de forma independiente:

- `m5stack-core2`.
- `m5stack-cores3`.

Cada ejecución conserva durante 14 días:

- Binarios `.bin`.
- Ejecutable `.elf`.
- Mapa de memoria cuando esté disponible.
- Log completo de compilación.
- Informe de tamaño.

### Seguridad · Código y dependencias

Incluye:

- CodeQL con consultas `security-extended` para Python.
- Revisión de dependencias modificadas en pull requests.
- Auditoría semanal de paquetes Python con `pip-audit`.

## Cómo localizar un fallo

1. Abre la ejecución fallida en la pestaña **Actions**.
2. Localiza el primer trabajo rojo.
3. Abre el primer paso rojo dentro de ese trabajo.
4. Busca la primera línea marcada como `error`, `FAILED` o `fatal error`.
5. Consulta el resumen generado al final del trabajo.
6. Descarga el artefacto de informes o logs cuando el mensaje visible no sea suficiente.

Los errores posteriores al primero suelen ser consecuencias, especialmente durante la compilación C++.

## Reglas de protección recomendadas para `main`

En **Settings > Rules > Rulesets**, exige antes de integrar:

- `Python 3.11 · calidad y pruebas`.
- `Python 3.12 · calidad y pruebas`.
- `Python 3.13 · calidad y pruebas`.
- `M5Stack Core2 · compilar firmware`.
- `M5Stack CoreS3 · compilar firmware`.
- `CodeQL · Python`.
- Un pull request aprobado.
- Conversaciones resueltas.
- Rama actualizada antes de fusionar.

## Seguridad adicional recomendada

Activa en **Settings > Code security**:

- Dependency graph.
- Dependabot alerts.
- Dependabot security updates.
- Secret scanning.
- Push protection.
- Code scanning con CodeQL.
