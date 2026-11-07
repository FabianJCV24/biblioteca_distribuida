"""Pruebas reproducibles sobre sockets reales y un servidor aislado."""
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from protocolo import enviar, recibir, MAX_MENSAJE
from rpc_cliente import ClienteRPC
from servidor import ServidorBiblioteca


def simultaneos(funciones):
    barrera = threading.Barrier(len(funciones))

    def ejecutar(funcion):
        barrera.wait(timeout=5)
        return funcion()

    with ThreadPoolExecutor(max_workers=len(funciones)) as ejecutor:
        futuros = [ejecutor.submit(ejecutar, funcion) for funcion in funciones]
        return [futuro.result(timeout=15) for futuro in futuros]


def main():
    servidor = ServidorBiblioteca(puerto=0)
    servidor.iniciar()
    hilo = threading.Thread(target=servidor.servir)
    hilo.start()
    rpc = ClienteRPC(puerto=servidor.puerto)
    fallos = 0

    def verificar(nombre, esperado, prueba):
        nonlocal fallos
        print(f'\n{nombre}\nEsperado: {esperado}')
        try:
            valido, obtenido = prueba()
        except Exception as exc:
            valido, obtenido = False, repr(exc)
        print(f'Obtenido: {obtenido}')
        print('APROBADA' if valido else 'FALLIDA')
        if not valido:
            fallos += 1

    def consultas():
        # Tres conexiones ya abiertas antes de liberar la barrera garantizan
        # al menos tres clientes conectados durante esta prueba.
        conexiones = [socket.create_connection(('127.0.0.1', servidor.puerto), timeout=5) for _ in range(3)]
        archivos = [conexion.makefile('rwb') for conexion in conexiones]
        def consultar(archivo):
            enviar(archivo, {'operacion': 'consultar_libros'})
            return recibir(archivo)
        try:
            resultados = simultaneos([lambda archivo=archivo: consultar(archivo) for archivo in archivos])
            valido = all(r['ok'] and len(r['datos']) >= 5 for r in resultados)
            valido = valido and resultados[0]['datos'] == resultados[1]['datos'] == resultados[2]['datos']
            return valido, resultados
        finally:
            for archivo in archivos:
                archivo.close()
            for conexion in conexiones:
                conexion.close()

    def reservas():
        resultados = simultaneos([lambda: rpc.reservar_libro(1), lambda: rpc.reservar_libro(1)])
        final = rpc.consultar_libro(1)
        valido = sorted(r['codigo'] for r in resultados) == ['RESERVA_EXITOSA', 'SIN_EJEMPLARES']
        valido = valido and sum(r['ok'] is True for r in resultados) == 1
        valido = valido and final['datos']['disponibles'] == 0
        return valido, dict(reservas=resultados, libro_final=final)

    def inexistente():
        r = rpc.consultar_libro(99999)
        return r['ok'] is False and r['codigo'] == 'LIBRO_INEXISTENTE', r

    def desconexion():
        with socket.create_connection(('127.0.0.1', servidor.puerto), timeout=5) as conexion:
            conexion.sendall(b'{"operacion":"consultar_libros"}\n')
            conexion.shutdown(socket.SHUT_RDWR)
        r = rpc.estado_servidor()
        return r['ok'] and r['datos']['activo'] and hilo.is_alive(), r

    def desconocida():
        r = rpc.llamar('operacion_inventada')
        return r['ok'] is False and r['codigo'] == 'OPERACION_DESCONOCIDA', r

    def protocolo():
        resultados = []
        with socket.create_connection(('127.0.0.1', servidor.puerto), timeout=5) as conexion:
            with conexion.makefile('rwb') as archivo:
                # JSON inválido y después dos mensajes en el mismo envío.
                archivo.write(b'no es json\n{"operacion":"consultar_libro","id":true}\n{"operacion":"estado_servidor"}\n')
                archivo.flush()
                resultados = [recibir(archivo) for _ in range(3)]
        with socket.create_connection(('127.0.0.1', servidor.puerto), timeout=5) as conexion:
            with conexion.makefile('rwb') as archivo:
                archivo.write(b'x' * (MAX_MENSAJE + 2) + b'\n')
                archivo.flush()
                resultados.append(recibir(archivo))
        return [r['codigo'] for r in resultados] == ['JSON_INVALIDO', 'ID_INVALIDO', 'OK', 'MENSAJE_GRANDE'], resultados

    try:
        verificar('Prueba 1: consultas simultáneas (tres clientes)', 'Tres catálogos iguales de al menos cinco libros.', consultas)
        verificar('Prueba 2: competencia por el último ejemplar', 'Una reserva exitosa, otra sin ejemplares; disponibilidad final cero.', reservas)
        verificar('Prueba 3: libro inexistente', 'Error LIBRO_INEXISTENTE.', inexistente)
        verificar('Prueba 4: desconexión anticipada', 'El servidor sigue activo y responde a otro cliente.', desconexion)
        verificar('Prueba 5: operación desconocida', 'Error OPERACION_DESCONOCIDA.', desconocida)
        verificar('Prueba adicional: validación y encuadre JSON Lines', 'Errores controlados y múltiples mensajes por conexión.', protocolo)
    finally:
        servidor.detener()
        hilo.join(timeout=5)
    if hilo.is_alive() or servidor.hilos:
        print('FALLIDA: quedaron hilos del servidor activos.')
        fallos += 1
    print(f'\nResultado: {fallos} prueba(s) fallida(s).')
    return 1 if fallos else 0


if __name__ == '__main__':
    raise SystemExit(main())
