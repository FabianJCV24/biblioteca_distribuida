"""Mensajes JSON Lines UTF-8 compartidos por servidor y clientes."""
import json

MAX_MENSAJE = 64 * 1024
TIEMPO_ESPERA = 10
FIN_CONEXION = object()


class ErrorProtocolo(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo


def respuesta(ok, codigo, mensaje, datos=None):
    return dict(ok=ok, codigo=codigo, mensaje=mensaje, datos=datos)


def enviar(archivo, mensaje):
    contenido = json.dumps(mensaje, ensure_ascii=False, allow_nan=False).encode('utf-8')
    if len(contenido) > MAX_MENSAJE:
        raise ErrorProtocolo('MENSAJE_GRANDE', 'Mensaje demasiado grande.')
    archivo.write(contenido + b'\n')
    archivo.flush()


def recibir(archivo):
    linea = archivo.readline(MAX_MENSAJE + 2)
    if not linea:
        return FIN_CONEXION
    if len(linea) > MAX_MENSAJE + 1:
        raise ErrorProtocolo('MENSAJE_GRANDE', 'Mensaje demasiado grande.')
    if not linea.endswith(b'\n'):
        raise ErrorProtocolo('MENSAJE_INCOMPLETO', 'Falta el salto de línea final.')
    try:
        return json.loads(linea.decode('utf-8'), parse_constant=_rechazar_constante)
    except (UnicodeError, ValueError) as exc:
        raise ErrorProtocolo('JSON_INVALIDO', 'Se requiere JSON válido en UTF-8.') from exc


def _rechazar_constante(valor):
    raise ValueError(valor)
