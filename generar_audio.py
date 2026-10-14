import asyncio
import os
import random
import sys

import edge_tts
import edge_tts.communicate as _edge_comm
import edge_tts.constants as _edge_const

# Microsoft responde 403 en el WebSocket viejo (oct 2026).
# El host nuevo acepta el mismo token. Quitar esto cuando edge-tts >= 7.2.9 lo traiga de serie.
_nuevo_wss = (
    "wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1"
    f"?Ocp-Apim-Subscription-Key={_edge_const.TRUSTED_CLIENT_TOKEN}"
)
_edge_const.WSS_URL = _nuevo_wss
_edge_comm.WSS_URL = _nuevo_wss

texto = sys.argv[1]
id_ejecucion = sys.argv[2]
indice = sys.argv[3]
voz = "es-CR-JuanNeural"
ritmo = "+8%"

carpeta = id_ejecucion
archivo_salida = f"{carpeta}/escena_{indice}.mp3"

# Si Microsoft responde con error (por ejemplo 429 = demasiados pedidos),
# se reintenta esperando cada vez un poco mas: ~5s, 10s, 20s, 40s, 60s.
MAX_INTENTOS = 6


def borrar_archivo_parcial():
    if os.path.exists(archivo_salida):
        try:
            os.remove(archivo_salida)
        except OSError:
            pass


async def main():
    os.makedirs(carpeta, exist_ok=True)
    ultimo_error = None

    for intento in range(1, MAX_INTENTOS + 1):
        try:
            communicate = edge_tts.Communicate(texto, voz, rate=ritmo)
            await communicate.save(archivo_salida)

            if os.path.exists(archivo_salida) and os.path.getsize(archivo_salida) > 0:
                print(f"Audio generado correctamente en el intento {intento}.")
                return
            raise RuntimeError("El archivo de audio quedo vacio")

        except Exception as e:
            ultimo_error = e
            print(f"Intento {intento}/{MAX_INTENTOS} fallo: {type(e).__name__}: {e}")
            borrar_archivo_parcial()

            if intento < MAX_INTENTOS:
                espera = min(60, 5 * 2 ** (intento - 1)) + random.uniform(0, 5)
                print(f"Esperando {espera:.0f} segundos antes de reintentar...")
                await asyncio.sleep(espera)

    print("Se agotaron los intentos, no se pudo generar el audio.")
    raise ultimo_error


asyncio.run(main())
