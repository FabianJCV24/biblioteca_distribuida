# Sistema Distribuido de Biblioteca Universitaria

Práctica académica con Python 3, sockets TCP, hilos, RPC y JSON Lines. No requiere paquetes externos ni base de datos. Recomendado: Python 3.10 o posterior y Visual Studio Code con la extensión Python.

## Archivos

- `servidor.py`: catálogo en memoria, un hilo por conexión, operaciones y cierre ordenado.
- `cliente.py`: menú interactivo con validación de entradas y errores de conexión.
- `rpc_cliente.py`: clase `ClienteRPC` con funciones que ocultan el transporte TCP.
- `protocolo.py`: lectura y escritura JSON Lines, respuestas uniformes y límites.
- `pruebas_concurrencia.py`: cinco casos obligatorios y una prueba adicional de protocolo.

## Ejecutar en Visual Studio Code

Abra una terminal dentro de esta misma carpeta. Compruebe `py --version` (en otros sistemas puede utilizar `python` o `python3` en lugar de `py`). Si no existe el comando, instale Python 3 y seleccione su intérprete en VS Code con **Python: Select Interpreter**.

Durante la verificación se utilizó Python portátil 3.12.10 porque este equipo no tenía Python en el PATH. Mientras conserve esa carpeta temporal, puede sustituir `py` en los comandos por `& "$env:TEMP\biblioteca-python-3.12\python.exe" -X utf8`. Por ejemplo:

```powershell
& "$env:TEMP\biblioteca-python-3.12\python.exe" -X utf8 servidor.py
```

Para uso permanente conviene instalar Python normalmente. La ejecución verificada de los seis casos está guardada en `evidencia_pruebas.txt`; también se comprobó el menú interactivo y su manejo del servidor desconectado.

Terminal 1:

```powershell
py servidor.py
```

Terminales 2, 3 y 4, cada una por separado:

```powershell
py cliente.py
```

El menú permite listar libros, consultar por ID, reservar, consultar estado y salir. El libro 1 empieza con un ejemplar. Detenga los clientes con la opción 5 y el servidor con Ctrl+C. El servidor deja de aceptar conexiones, cierra sockets y espera a sus hilos.

Para trabajar entre máquinas, inicie el servidor con:

```powershell
py servidor.py --host 0.0.0.0 --puerto 5000
```

En cada cliente indique la IP local real de la máquina servidora:

```powershell
py cliente.py --host 192.168.1.10 --puerto 5000
```

Ambas máquinas deben tener conectividad y el firewall debe permitir TCP en el puerto elegido. `0.0.0.0` es una dirección de escucha, no la dirección que debe introducir el cliente. Esta práctica transmite datos sin autenticación ni cifrado; utilícela en una red de laboratorio de confianza.

## Pruebas automáticas y evidencias

```powershell
py pruebas_concurrencia.py
```

No es necesario iniciar el servidor manualmente. Cada ejecución crea un servidor independiente en localhost con un puerto libre y catálogo nuevo; no modifica el servidor de sus clientes interactivos. Se ejecutan:

1. Consultas simultáneas de tres clientes con conexiones abiertas y barrera de inicio.
2. Dos clientes liberados por una barrera compiten por el último ejemplar. Se verifica exactamente un éxito, un error y disponibilidad final cero.
3. Consulta de ID inexistente.
4. Desconexión antes de leer la respuesta, seguida de una consulta de estado.
5. Operación desconocida.
6. Validación adicional de JSON inválido, ID booleano, varios mensajes por conexión y mensaje excesivo.

Cada caso imprime lo esperado, lo obtenido y APROBADA o FALLIDA. El proceso devuelve código 0 si todo pasa y 1 si hay fallos. También comprueba que los hilos terminen al detenerse.

Para guardar evidencia del informe:

```powershell
py pruebas_concurrencia.py 2>&1 | Tee-Object -FilePath evidencia_pruebas.txt
$LASTEXITCODE
```

Capture las terminales del servidor (conexiones y operaciones), varios clientes y las pruebas. En el informe incluya la versión de Python, comandos, resultados completos y una explicación de la carrera por el último ejemplar. Puede ejecutar las pruebas varias veces para demostrar que los datos se reinician y el resultado se repite.

## Operaciones RPC

| Función de `ClienteRPC` | Solicitud | Resultado |
| --- | --- | --- |
| `consultar_libros()` | `{"operacion":"consultar_libros"}` | Lista del catálogo |
| `consultar_libro(1)` | `{"operacion":"consultar_libro","id":1}` | Datos del libro |
| `reservar_libro(1)` | `{"operacion":"reservar_libro","id":1}` | Confirmación y nueva disponibilidad |
| `estado_servidor()` | `{"operacion":"estado_servidor"}` | Activo, conexiones atendidas acumuladas y conexiones activas |

Cada llamada RPC abre y cierra una conexión. `clientes_atendidos` cuenta conexiones aceptadas, no personas ni usuarios únicos. El servidor también admite varias solicitudes consecutivas en una conexión.

Ejemplo de uso desde Python:

```python
from rpc_cliente import ClienteRPC
rpc = ClienteRPC()
print(rpc.consultar_libros())
print(rpc.reservar_libro(1))
```

## Protocolo y sincronización

TCP transporta bytes, sin conservar los límites entre mensajes. Por eso cada mensaje es un objeto JSON codificado en UTF-8 y terminado en `\n`. La lectura acumula hasta ese salto, incluso si TCP fragmenta el mensaje, y conserva mensajes posteriores. El límite es 64 KiB de contenido por mensaje; el tiempo de espera de comunicación es 10 segundos. Una conexión inactiva puede cerrarse al superar ese plazo.

Todas las respuestas contienen `ok`, `codigo`, `mensaje` y `datos` (null si no corresponde). Códigos: `OK`, `RESERVA_EXITOSA`, `LIBRO_INEXISTENTE`, `SIN_EJEMPLARES`, `OPERACION_DESCONOCIDA`, `JSON_INVALIDO`, `SOLICITUD_INVALIDA`, `ID_INVALIDO`, `MENSAJE_GRANDE`, `MENSAJE_INCOMPLETO` y `ERROR_INTERNO`. Los IDs deben ser enteros positivos; booleanos, texto y decimales se rechazan. JSON inválido permite continuar la conexión; mensajes excesivos o incompletos provocan su cierre.

Un `threading.Lock` compartido protege tanto la comprobación de disponibilidad como el descuento. Si dos hilos intentan reservar el último ejemplar, uno entra primero, observa 1 y lo reduce a 0; el segundo entra después y recibe `SIN_EJEMPLARES`. El descuento nunca se realiza cuando la cantidad es cero. Las consultas copian datos bajo el mismo Lock para devolver una vista coherente sin exponer referencias modificables.

Si el servidor se desconecta o vence el tiempo de espera, la capa RPC lanza `ErrorRPC` y el menú muestra el error y permite reintentar. Una reserva cuya respuesta se pierde puede haberse aplicado: el cliente no la reintenta automáticamente. Los datos están únicamente en memoria y vuelven al catálogo inicial al reiniciar el servidor.
