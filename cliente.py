"""Menú de consola para la biblioteca distribuida."""
import argparse
from rpc_cliente import ClienteRPC, ErrorRPC


def mostrar(resultado):
    print(f"\n[{resultado['codigo']}] {resultado['mensaje']}")
    datos = resultado['datos']
    if isinstance(datos, list):
        for libro in datos:
            mostrar_libro(libro)
    elif isinstance(datos, dict):
        if 'titulo' in datos:
            mostrar_libro(datos)
        else:
            for clave, valor in datos.items():
                print(f'  {clave}: {valor}')


def mostrar_libro(libro):
    print(f"  {libro['id']}. {libro['titulo']} — {libro['autor']} | Disponibles: {libro['disponibles']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--puerto', type=int, default=5000)
    args = parser.parse_args()
    rpc = ClienteRPC(args.host, args.puerto)
    while True:
        try:
            print('\n1. Consultar todos los libros\n2. Consultar un libro por ID\n3. Reservar un libro\n4. Consultar estado del servidor\n5. Salir')
            opcion = input('Seleccione una opción: ').strip()
            if opcion == '5':
                break
            if opcion == '1':
                resultado = rpc.consultar_libros()
            elif opcion in ('2', '3'):
                try:
                    id = int(input('ID del libro: '))
                    if id <= 0:
                        raise ValueError
                except ValueError:
                    print('Introduzca un entero positivo.')
                    continue
                resultado = rpc.consultar_libro(id) if opcion == '2' else rpc.reservar_libro(id)
            elif opcion == '4':
                resultado = rpc.estado_servidor()
            else:
                print('Opción inválida.')
                continue
            mostrar(resultado)
        except ErrorRPC as exc:
            print(f'Error: {exc}. Puede volver a intentarlo desde el menú.')
        except (EOFError, KeyboardInterrupt):
            break
    print('\nCliente cerrado.')


if __name__ == '__main__':
    main()
