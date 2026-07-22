"""Transporte USB serie para mensajes NDJSON."""

# Conserva las anotaciones como texto para permitir importaciones solo de tipado.
from __future__ import annotations

# Importa utilidades estándar para declarar dependencias exclusivas del analizador estático.
from typing import TYPE_CHECKING

# Importa la clase real de pyserial únicamente durante el análisis de tipos.
if TYPE_CHECKING:
    # Proporciona a MyPy la definición exacta de la conexión serie.
    import serial


# Gestiona una conexión serie simple y explícita.
class SerialTransport:
    """Envía mensajes completos a un dispositivo conectado por USB serie."""

    # Inicializa la configuración sin abrir todavía el puerto.
    def __init__(self, port: str, baud_rate: int = 115_200, timeout: float = 1.0) -> None:
        """Guarda los parámetros necesarios para abrir el puerto."""

        # Guarda el nombre del puerto proporcionado por el usuario.
        self._port = port
        # Guarda la velocidad acordada con el firmware.
        self._baud_rate = baud_rate
        # Guarda el tiempo máximo de espera en operaciones de E/S.
        self._timeout = timeout
        # Inicializa la conexión real de pyserial como cerrada.
        self._connection: serial.Serial | None = None

    # Abre el puerto configurado cuando todavía está cerrado.
    def open(self) -> None:
        """Abre la conexión serie de forma idempotente."""

        # Evita abrir una segunda conexión sobre el mismo objeto.
        if self._connection is not None and self._connection.is_open:
            # Sale sin modificar una conexión ya válida.
            return
        # Importa pyserial solo cuando se necesita acceso físico al puerto.
        import serial

        # Crea y abre el puerto serie con los parámetros configurados.
        self._connection = serial.Serial(
            # Selecciona el puerto del M5Stack.
            port=self._port,
            # Configura la velocidad del protocolo.
            baudrate=self._baud_rate,
            # Configura el tiempo de espera de lectura y escritura.
            timeout=self._timeout,
            # Configura también el tiempo máximo de escritura.
            write_timeout=self._timeout,
        )

    # Escribe un mensaje completo y fuerza su salida.
    def send(self, payload: bytes) -> None:
        """Envía un mensaje ya codificado al dispositivo."""

        # Garantiza que la conexión esté abierta antes de escribir.
        self.open()
        # Comprueba la referencia para satisfacer el análisis estático.
        if self._connection is None:
            # Lanza un error imposible salvo fallo interno de apertura.
            raise RuntimeError("La conexión serie no está disponible.")
        # Escribe todos los bytes del mensaje.
        written = self._connection.write(payload)
        # Comprueba que el controlador aceptó el mensaje completo.
        if written != len(payload):
            # Informa de una escritura parcial para evitar estados corruptos.
            raise OSError("No se pudo transmitir el mensaje serie completo.")
        # Fuerza el envío inmediato del búfer de salida.
        self._connection.flush()

    # Cierra la conexión si se encuentra abierta.
    def close(self) -> None:
        """Libera el puerto serie de forma segura."""

        # Comprueba que exista una conexión abierta.
        if self._connection is not None and self._connection.is_open:
            # Cierra el descriptor del puerto.
            self._connection.close()
        # Elimina la referencia para permitir una apertura posterior limpia.
        self._connection = None

    # Permite utilizar el transporte mediante un bloque with.
    def __enter__(self) -> SerialTransport:
        """Abre el transporte y devuelve la instancia activa."""

        # Abre la conexión serie configurada.
        self.open()
        # Devuelve la instancia para el bloque de contexto.
        return self

    # Garantiza el cierre al abandonar un bloque with.
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Cierra el transporte independientemente del resultado del bloque."""

        # Libera siempre el puerto serie.
        self.close()
