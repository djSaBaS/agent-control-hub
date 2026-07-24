# Política de seguridad

## Versiones soportadas

Agent Control Hub está en fase de prototipo. Solo la rama `main` y la última versión publicada reciben correcciones de seguridad.

| Versión | Soporte de seguridad |
|---|---|
| `main` | Sí |
| Versiones anteriores | No garantizado |

## Cómo informar de una vulnerabilidad

No publiques credenciales, volcados de sesiones, bases de datos de Hermes, archivos JSONL de Codex ni detalles explotables en una incidencia pública.

Utiliza, por este orden:

1. **Private vulnerability reporting** del repositorio, cuando esté habilitado en GitHub.
2. Un contacto privado con el propietario del repositorio.
3. Una incidencia pública únicamente para indicar que existe un posible problema, sin incluir secretos, pruebas explotables ni datos personales.

Incluye, cuando sea posible:

- componente afectado;
- versión o commit;
- impacto previsto;
- pasos mínimos de reproducción sanitizados;
- medidas temporales de contención;
- propuesta de corrección.

## Plazos orientativos

- Acuse de recibo: 3 días laborables.
- Clasificación inicial: 7 días laborables.
- Corrección crítica: objetivo de 14 días.
- Corrección alta: objetivo de 30 días.
- Corrección media o baja: siguiente ciclo razonable de mantenimiento.

Los plazos pueden cambiar durante la fase de prototipo, pero cualquier credencial expuesta debe revocarse inmediatamente.

## Datos que nunca deben subirse

- `.env` y variantes locales;
- `auth.json` de Hermes;
- `state.db`, `state.db-wal` o `state.db-shm`;
- `config.yaml` real de Hermes;
- sesiones JSONL completas de Codex;
- claves API, tokens, contraseñas o cookies;
- claves privadas, certificados con clave privada o archivos de firma;
- snapshots sin sanitizar;
- volcados de memoria o logs con conversaciones completas.

## Alcance de seguridad actual

El diseño soportado es:

- ejecución local;
- lectura pasiva de Codex y Hermes;
- visor restringido al propio equipo;
- transporte USB serie;
- dispositivo físico de solo lectura;
- acciones remotas desactivadas.

No se considera seguro, sin una revisión adicional:

- publicar el visor en Internet o en la red corporativa;
- activar acciones desde el dispositivo;
- aceptar comandos remotos;
- usar Wi-Fi o Bluetooth sin autenticación y cifrado;
- almacenar secretos en el ESP32;
- distribuir firmware de producción sin firma, Secure Boot y una política de claves.

## Respuesta ante una exposición de secretos

1. Revocar o rotar la credencial.
2. Detener el servicio afectado.
3. Eliminar el secreto del código y de los artefactos.
4. Revisar el historial del repositorio y los logs de uso.
5. Considerar comprometida la credencial aunque el commit se haya borrado.
6. Documentar la causa y añadir una prueba preventiva.
