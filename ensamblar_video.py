import subprocess
import json
import sys
import os
import glob
import random
import textwrap

id_ejecucion = sys.argv[1]
carpeta = id_ejecucion
transicion = 0.5

TRANSICIONES_POSIBLES = [
    "fade", "fadeblack", "fadewhite",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "circleopen", "circleclose",
    "smoothleft", "smoothright"
]
transicion_tipo = random.choice(TRANSICIONES_POSIBLES)
print(f"Transicion elegida para este video: {transicion_tipo}")

FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def duracion_audio(ruta):
    resultado = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", ruta],
        capture_output=True, text=True
    )
    datos = json.loads(resultado.stdout)
    return float(datos["format"]["duration"])

def escapar_texto_ffmpeg(texto):
    texto = texto.replace("\\", "\\\\")
    texto = texto.replace(":", "\\:")
    texto = texto.replace("'", "\u2019")
    texto = texto.replace("%", "\\%")
    return texto

def armar_texto_multilinea(texto, ancho=28):
    lineas = textwrap.wrap(texto, width=ancho)
    return "\n".join(lineas)

# Cargar el texto de cada escena
with open(f"{carpeta}/escenas.json", "r", encoding="utf-8") as f:
    escenas = json.load(f)

imagenes = sorted(glob.glob(f"{carpeta}/escena_*.jpg"),
                   key=lambda x: int(x.split("_")[-1].split(".")[0]))
n = len(imagenes)
print(f"Escenas detectadas: {n}")

duraciones = []
for i in range(n):
    dur = duracion_audio(f"{carpeta}/escena_{i}.mp3")
    duraciones.append(dur)
    print(f"Escena {i}: {dur:.2f}s")

clips = []
for i in range(n):
    dur = duraciones[i]
    dur_clip = dur if i == n - 1 else dur + transicion
    frames = int(dur_clip * 30)
    zoom_expr = "min(zoom+0.0012,1.2)"
    clip_out = f"{carpeta}/clip_{i}.mp4"

    texto_escena = armar_texto_multilinea(escenas[i]["texto"])
    texto_escapado = escapar_texto_ffmpeg(texto_escena)
    texto_escapado = texto_escapado.replace("\n", "\\n")

    filtro_texto = (
        f"drawtext=fontfile={FUENTE}:text='{texto_escapado}':"
        f"fontcolor=white:fontsize=52:borderw=3:bordercolor=black:"
        f"box=1:boxcolor=black@0.35:boxborderw=20:"
        f"x=(w-text_w)/2:y=h*0.72:line_spacing=10"
    )

    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-i", f"{carpeta}/escena_{i}.jpg",
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z='{zoom_expr}':d={frames}:s=1080x1920:fps=30,{filtro_texto}",
        "-t", str(dur_clip), "-pix_fmt", "yuv420p", clip_out
    ], check=True)
    clips.append(clip_out)

if n == 1:
    subprocess.run(["cp", clips[0], f"{carpeta}/video_mudo.mp4"], check=True)
else:
    inputs = []
    for c in clips:
        inputs += ["-i", c]

    filtro = ""
    offset = duraciones[0]
    salida_actual = "[0:v]"
    for i in range(1, n):
        etiqueta_salida = f"[v{i}]" if i < n - 1 else "[vout]"
        filtro += f"{salida_actual}[{i}:v]xfade=transition={transicion_tipo}:duration={transicion}:offset={offset - transicion}{etiqueta_salida};"
        salida_actual = etiqueta_salida
        if i < n - 1:
            offset += duraciones[i]

    filtro = filtro.rstrip(";")
    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filtro,
        "-map", "[vout]", f"{carpeta}/video_mudo.mp4"
    ]
    subprocess.run(cmd, check=True)

with open(f"{carpeta}/lista_audio.txt", "w") as f:
    for i in range(n):
        f.write(f"file 'escena_{i}.mp3'\n")

subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
    "-i", f"{carpeta}/lista_audio.txt", "-c", "copy",
    f"{carpeta}/narracion_completa.mp3"
], check=True)

musica_path = f"{carpeta}/musica.mp3"
if os.path.exists(musica_path):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", f"{carpeta}/narracion_completa.mp3",
        "-i", musica_path,
        "-filter_complex",
        "[0:a]volume=1.2[narracion_alta];[1:a]volume=0.18[musica_alta];[narracion_alta][musica_alta]amix=inputs=2:duration=first:dropout_transition=2[audio_final]",
        "-map", "[audio_final]",
        f"{carpeta}/audio_final.mp3"
    ], check=True)
else:
    subprocess.run(["cp", f"{carpeta}/narracion_completa.mp3", f"{carpeta}/audio_final.mp3"], check=True)

subprocess.run([
    "ffmpeg", "-y",
    "-i", f"{carpeta}/video_mudo.mp4",
    "-i", f"{carpeta}/audio_final.mp3",
    "-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
    "-movflags", "+faststart",
    "-shortest",
    f"{carpeta}/video_final.mp4"
], check=True)

print("Video final generado correctamente.")
