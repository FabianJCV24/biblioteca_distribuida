"""Funciones RPC: cada llamada utiliza una conexión TCP independiente."""
import socket
from protocolo import ErrorProtocolo, TIEMPO_ESPERA, enviar, recibir


class ErrorRPC(Exception):
    pass


class ClienteRPC:
    def __init__(self, host='127.0.0.1', puerto=5000, timeout=TIEMPO_ESPERA):
        self.host, self.puerto, self.timeout = host, puerto, timeout

    def llamar(self, operacion, **parametros):
        try:
            with socket.create_connection((self.host, self.puerto), timeout=self.timeout) as conexion:
                with conexion.makefile('rwb') as archivo:
                    enviar(archivo, dict(operacion=operacion, **parametros))
                    resultado = recibir(archivo)
                    if not isinstance(resultado, dict) or not all(
                        campo in resultado for campo in ('ok', 'codigo', 'mensaje', 'datos')
                    ):
                        raise ErrorRPC('El servidor cerró la conexión o respondió incorrectamente.')
                    return resultado
        except (OSError, ErrorProtocolo) as exc:
            raise ErrorRPC(f'No se pudo completar la comunicación: {exc}') from exc

    def consultar_libros(self):
        return self.llamar('consultar_libros')

    def consultar_libro(self, id):
        return self.llamar('consultar_libro', id=id)

    def reservar_libro(self, id):
        return self.llamar('reservar_libro', id=id)

    def estado_servidor(self):
        return self.llamar('estado_servidor')
