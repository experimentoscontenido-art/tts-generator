import edge_tts
import asyncio
import sys
import os

texto = sys.argv[1]
id_ejecucion = sys.argv[2]
indice = sys.argv[3]
voz = "es-CR-JuanNeural"

carpeta = id_ejecucion
archivo_salida = f"{carpeta}/escena_{indice}.mp3"

async def main():
    os.makedirs(carpeta, exist_ok=True)
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save(archivo_salida)

asyncio.run(main())
