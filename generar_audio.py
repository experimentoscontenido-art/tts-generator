import edge_tts
import edge_tts.communicate as _edge_comm
import edge_tts.constants as _edge_const
import asyncio
import sys
import os

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

async def main():
    os.makedirs(carpeta, exist_ok=True)
    communicate = edge_tts.Communicate(texto, voz, rate=ritmo)
    await communicate.save(archivo_salida)

asyncio.run(main())
