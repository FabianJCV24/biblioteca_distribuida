"""Servidor TCP concurrente de biblioteca, sin dependencias externas."""
import argparse
import logging
import socket
import threading

from protocolo import ErrorProtocolo, FIN_CONEXION, TIEMPO_ESPERA, enviar, recibir, respuesta

LOG = logging.getLogger('biblioteca')


class ServidorBiblioteca:
    def __init__(self, host='127.0.0.1', puerto=5000):
        self.host, self.puerto = host, puerto
        self.lock = threading.Lock()
        self.libros = {
            1: dict(id=1, titulo='Sistemas distribuidos', autor='Andrew S. Tanenbaum', disponibles=1),
            2: dict(id=2, titulo='Redes de computadoras', autor='Andrew S. Tanenbaum', disponibles=3),
            3: dict(id=3, titulo='Sistemas operativos modernos', autor='Andrew S. Tanenbaum', disponibles=4),
            4: dict(id=4, titulo='Introducción a los algoritmos', autor='Thomas H. Cormen', disponibles=2),
            5: dict(id=5, titulo='Python para todos', autor='Charles Severance', disponibles=5),
        }
        self.activo = threading.Event()
        self.clientes_atendidos = 0
        self.conexiones = set()
        self.hilos = set()
        self.socket = None

    def iniciar(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.puerto))
            self.socket.listen()
            self.socket.settimeout(0.5)
            self.puerto = self.socket.getsockname()[1]
            self.activo.set()
        except Exception:
            self.socket.close()
            raise
        LOG.info('Servidor escuchando en %s:%s', self.host, self.puerto)

    def servir(self):
        if self.socket is None:
            self.iniciar()
        try:
            while self.activo.is_set():
                try:
                    conexion, direccion = self.socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self.activo.is_set():
                        raise
                    break
                conexion.settimeout(TIEMPO_ESPERA)
                hilo = threading.Thread(target=self._atender, args=(conexion, direccion))
                with self.lock:
                    self.clientes_atendidos += 1
                    self.conexiones.add(conexion)
                    self.hilos.add(hilo)
                hilo.start()
        finally:
            self.detener()

    def detener(self):
        self.activo.clear()
        if self.socket is not None:
            self.socket.close()
        with self.lock:
            conexiones = list(self.conexiones)
            hilos = list(self.hilos)
        for conexion in conexiones:
            try:
                conexion.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            conexion.close()
        for hilo in hilos:
            if hilo is not threading.current_thread():
                hilo.join()
        LOG.info('Servidor detenido.')

    def _atender(self, conexion, direccion):
        LOG.info('Cliente conectado: %s', direccion)
        try:
            with conexion, conexion.makefile('rwb') as archivo:
                while self.activo.is_set():
                    try:
                        solicitud = recibir(archivo)
                    except ErrorProtocolo as exc:
                        enviar(archivo, respuesta(False, exc.codigo, str(exc)))
                        # Un mensaje excesivo puede dejar bytes sin consumir: cerrar.
                        if exc.codigo != 'JSON_INVALIDO':
                            break
                        continue
                    if solicitud is FIN_CONEXION:
                        break
                    try:
                        resultado = self.ejecutar(solicitud)
                    except Exception:
                        LOG.exception('Error interno')
                        resultado = respuesta(False, 'ERROR_INTERNO', 'Error interno del servidor.')
                    enviar(archivo, resultado)
        except (OSError, ErrorProtocolo) as exc:
            LOG.info('Conexión finalizada %s: %s', direccion, exc)
        finally:
            with self.lock:
                self.conexiones.discard(conexion)
                self.hilos.discard(threading.current_thread())
            LOG.info('Cliente desconectado: %s', direccion)

    def ejecutar(self, solicitud):
        if not isinstance(solicitud, dict) or not isinstance(solicitud.get('operacion'), str):
            return respuesta(False, 'SOLICITUD_INVALIDA', 'Indique una operación de texto.')
        operacion = solicitud['operacion']
        LOG.info('Operación: %s', operacion)
        if operacion not in ('consultar_libros', 'consultar_libro', 'reservar_libro', 'estado_servidor'):
            return respuesta(False, 'OPERACION_DESCONOCIDA', 'La operación no existe.')
        if operacion in ('consultar_libro', 'reservar_libro'):
            identificador = solicitud.get('id')
            if type(identificador) is not int or identificador <= 0:
                return respuesta(False, 'ID_INVALIDO', 'El ID debe ser un entero positivo.')
        # La comprobación y el descuento forman una sola sección crítica.
        # Sin Lock, dos hilos podrían observar el último ejemplar y reservarlo.
        # También copiamos las lecturas bajo el mismo Lock para obtener datos coherentes.
        with self.lock:
            if operacion == 'estado_servidor':
                return respuesta(True, 'OK', 'Estado del servidor.', dict(
                    activo=self.activo.is_set(), clientes_atendidos=self.clientes_atendidos,
                    clientes_activos=len(self.conexiones)))
            if operacion == 'consultar_libros':
                return respuesta(True, 'OK', 'Catálogo disponible.', [dict(x) for x in self.libros.values()])
            libro = self.libros.get(identificador)
            if libro is None:
                return respuesta(False, 'LIBRO_INEXISTENTE', 'El libro no existe.')
            if operacion == 'reservar_libro':
                if libro['disponibles'] == 0:
                    return respuesta(False, 'SIN_EJEMPLARES', 'No hay ejemplares disponibles.', dict(libro))
                libro['disponibles'] -= 1
                return respuesta(True, 'RESERVA_EXITOSA', 'Reserva confirmada.', dict(libro))
            return respuesta(True, 'OK', 'Libro encontrado.', dict(libro))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--puerto', type=int, default=5000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    servidor = ServidorBiblioteca(args.host, args.puerto)
    try:
        servidor.servir()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        LOG.error('No se pudo ejecutar el servidor: %s', exc)
        return 1
    finally:
        servidor.detener()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
