import edge_tts
import asyncio
import sys

texto = sys.argv[1]
voz = "es-AR-ElenaNeural"

async def main():
    communicate = edge_tts.Communicate(texto, voz)
    await communicate.save("output.mp3")

asyncio.run(main())
