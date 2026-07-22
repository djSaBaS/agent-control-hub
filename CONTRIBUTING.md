# Contribuir

## Flujo de trabajo

1. Abre una incidencia describiendo el cambio.
2. Crea una rama desde `main`.
3. Mantén los adaptadores aislados del protocolo del dispositivo.
4. Añade pruebas para toda lógica nueva.
5. No incluyas claves, tokens, cookies ni credenciales.
6. Ejecuta las validaciones antes de proponer el cambio.

## Validaciones del servicio

```powershell
cd service
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest
```

## Validación del firmware

```powershell
cd firmware/core2
pio run
```

## Convenciones

- Código y documentación técnica en inglés cuando sea necesario para interoperabilidad.
- Interfaz de usuario y documentación principal en español.
- Los valores ausentes se representan como `null`; no se estiman silenciosamente.
- Las estimaciones deben incluir su origen y nivel de confianza.
