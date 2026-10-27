import asyncio
import os
import random
import re
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

voz = "es-CR-JuanNeural"
ritmo = "+8%"

# Si Microsoft responde con error (por ejemplo 429 = demasiados pedidos),
# se reintenta esperando cada vez un poco mas: ~5s, 10s, 20s, 40s, 60s.
MAX_INTENTOS = 6

# ---------------------------------------------------------------------------
# DICCIONARIO DE PRONUNCIACION
# Palabra (o nombre) como aparece en el texto -> como tiene que sonar.
# Solo afecta a la VOZ: los subtitulos del video siguen mostrando el texto original.
# Para agregar una palabra nueva, suma una linea:  "palabra": "como suena",
# ---------------------------------------------------------------------------
PRONUNCIACIONES = {
    "like": "laik",
    "likes": "laiks",
    "Wi-Fi": "guai fai",
    "WiFi": "guai fai",
    "CienciaMente": "Ciencia Mente",
}

# Simbolos y unidades que se reemplazan tal cual (sin importar mayusculas).
UNIDADES = {
    "°C": " grados Celsius",
    "°F": " grados Fahrenheit",
    "km/h": " kilómetros por hora",
    "km²": " kilómetros cuadrados",
    "cm²": " centímetros cuadrados",
    "m²": " metros cuadrados",
}

# Abreviaturas de medida: (singular, plural). Se usa singular solo si el numero es exactamente 1.
MEDIDAS = {
    "km": ("kilómetro", "kilómetros"),
    "kg": ("kilogramo", "kilogramos"),
    "cm": ("centímetro", "centímetros"),
    "mm": ("milímetro", "milímetros"),
}

# Separadores de miles que no son punto ni coma: espacio comun, espacio de no separacion y espacios finos.
ESPACIOS_MILES = " \u00a0\u202f\u2009"


def _convertir_numero(m):
    """
    Arregla como se leen los numeros con puntos o comas.
    Reglas (convencion en español):
      - 13.000 / 1.250.000 / 13,000  -> separador de miles  -> 13000 / 1250000
      - 1.234,56                     -> 1234 punto 56
      - 1.3 / 1,3 / 0.125            -> decimal             -> 1 punto 3 / 0 punto 1 2 5
    Un grupo de exactamente 3 digitos despues del punto o la coma se toma como miles,
    salvo que el numero empiece con 0 (ahi es decimal: 0.125).
    """
    s = m.group(0)

    # 1.234,56  (miles con punto y decimal con coma)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+,\d+", s):
        entero, dec = s.split(",")
        entero = entero.replace(".", "")
        return f"{entero} punto {' '.join(dec) if len(dec) > 2 else dec}"

    # 13.000 / 1.250.000 / 13,000 / 1,250,000  (separador de miles)
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", s) and not s.startswith("0"):
        return re.sub(r"[.,]", "", s)

    # 1.3 / 1,3 / 3,14159 / 0.125  (decimal)
    if re.fullmatch(r"\d+[.,]\d+", s):
        entero, dec = re.split(r"[.,]", s)
        if len(dec) > 2:
            dec = " ".join(dec)  # digito por digito: 14159 -> 1 4 1 5 9
        return f"{entero} punto {dec}"

    return s


def _medida_singular(m):
    return "1 " + MEDIDAS[m.group(1).lower()][0]


def _medida_plural(m):
    return MEDIDAS[m.group(1).lower()][1]


def normalizar_para_voz(texto):
    # 0. Miles separados por espacio: "20 000" -> "20000" (solo si cada grupo tiene 3 digitos)
    texto = re.sub(
        r"(?<![\d.,])\d{1,3}(?:[" + ESPACIOS_MILES + r"]\d{3})+(?!\d)",
        lambda m: re.sub("[" + ESPACIOS_MILES + "]", "", m.group(0)),
        texto,
    )

    # 1. Numeros con puntos o comas
    texto = re.sub(r"\d+(?:[.,]\d+)*", _convertir_numero, texto)

    # 2. Porcentajes
    texto = re.sub(r"\s*%", " por ciento", texto)

    # 3. Unidades y simbolos
    for simbolo, lectura in UNIDADES.items():
        texto = re.sub(re.escape(simbolo), lectura, texto, flags=re.IGNORECASE)

    # 3b. Medidas (km, kg, cm, mm): singular si es exactamente 1, plural en el resto
    texto = re.sub(r"(\d)(km|kg|cm|mm)(?![\w/²])", r"\1 \2", texto, flags=re.IGNORECASE)  # 20000km -> 20000 km
    texto = re.sub(r"(?<![\w.,])1\s*(km|kg|cm|mm)(?![\w/²])", _medida_singular, texto, flags=re.IGNORECASE)
    texto = re.sub(r"(?<![^\W\d_])(km|kg|cm|mm)(?![\w/²])", _medida_plural, texto, flags=re.IGNORECASE)

    # 4. Pronunciacion de palabras y nombres
    for palabra, lectura in PRONUNCIACIONES.items():
        patron = r"(?<!\w)" + re.escape(palabra) + r"(?!\w)"
        texto = re.sub(patron, lectura, texto, flags=re.IGNORECASE)

    # 5. Limpiar espacios dobles que pueden quedar
    texto = re.sub(r"[ \t]{2,}", " ", texto).strip()

    return texto


def borrar_archivo_parcial(archivo_salida):
    if os.path.exists(archivo_salida):
        try:
            os.remove(archivo_salida)
        except OSError:
            pass


async def main(texto, carpeta, archivo_salida):
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
            borrar_archivo_parcial(archivo_salida)

            if intento < MAX_INTENTOS:
                espera = min(60, 5 * 2 ** (intento - 1)) + random.uniform(0, 5)
                print(f"Esperando {espera:.0f} segundos antes de reintentar...")
                await asyncio.sleep(espera)

    print("Se agotaron los intentos, no se pudo generar el audio.")
    raise ultimo_error


if __name__ == "__main__":
    texto = sys.argv[1]
    id_ejecucion = sys.argv[2]
    indice = sys.argv[3]

    carpeta = id_ejecucion
    archivo_salida = f"{carpeta}/escena_{indice}.mp3"

    texto_voz = normalizar_para_voz(texto)
    print(f"Texto original:  {texto}")
    print(f"Texto para voz:  {texto_voz}")

    asyncio.run(main(texto_voz, carpeta, archivo_salida))
