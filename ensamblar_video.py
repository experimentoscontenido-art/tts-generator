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

STICKERS_FIJOS = [
    {"archivo": "assets/stickers/seguime_facebook.png", "x": "W*0.50-w/2", "y": "150"},
    {"archivo": "assets/stickers/suscribete_youtube.png", "x": "W*0.50-w/2", "y": "500"},
    {"archivo": "assets/stickers/comenta.png", "x": "W*0.50-w/2", "y": "850"},
]

EFECTOS_TRANSICION = [
    "assets/efectos/efecto1.mp3",
    "assets/efectos/efecto2.mp3",
    "assets/efectos/efecto3.mp3",
]

def duracion_audio(ruta):
    resultado = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", ruta],
        capture_output=True, text=True
    )
    datos = json.loads(resultado.stdout)
    return float(datos["format"]["duration"])

def armar_texto_multilinea(texto, ancho=24, break_long_words=True):
    lineas = textwrap.wrap(texto, width=ancho, break_long_words=break_long_words)
    return "\n".join(lineas)

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
puntos_transicion = []

for i in range(n):
    dur = duraciones[i]
    dur_clip = dur if i == n - 1 else dur + transicion
    frames = int(dur_clip * 30)
    zoom_expr = "min(zoom+0.0012,1.2)"
    clip_out = f"{carpeta}/clip_{i}.mp4"

    texto_multilinea = armar_texto_multilinea(escenas[i]["texto"])
    archivo_subtitulo = f"{carpeta}/sub_{i}.txt"
    with open(archivo_subtitulo, "w", encoding="utf-8") as f_sub:
        f_sub.write(texto_multilinea)

    filtro_texto = (
        f"drawtext=fontfile={FUENTE}:textfile={archivo_subtitulo}:expansion=none:text_align=C:"
        f"fontcolor=white:fontsize=48:borderw=2:bordercolor=black:"
        f"box=1:boxcolor=black@0.4:boxborderw=14:"
        f"x=(w-text_w)/2:y=h*0.70:line_spacing=12"
    )

    hay_stickers = all(os.path.exists(s["archivo"]) for s in STICKERS_FIJOS)
    es_ultima_escena = (i == n - 1) and hay_stickers

    if es_ultima_escena:
        inputs_extra = []
        for s in STICKERS_FIJOS:
            inputs_extra += ["-loop", "1", "-i", s["archivo"]]

        velocidades = [round(random.uniform(1.5, 2.5), 1) for _ in STICKERS_FIJOS]

        filtro_partes = [
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
            f"zoompan=z='{zoom_expr}':d={frames}:s=1080x1920:fps=30,{filtro_texto}[base]"
        ]
        capa_actual = "[base]"
        for idx, sticker in enumerate(STICKERS_FIJOS):
            entrada_sticker = idx + 1
            etiqueta_sticker = f"[ic{idx}]"
            etiqueta_salida = f"[b{idx}]" if idx < len(STICKERS_FIJOS) - 1 else "[vout]"
            vel = velocidades[idx]
            filtro_partes.append(
                f"[{entrada_sticker}:v]scale=w='260+20*sin(2*PI*t*{vel})':h='260+20*sin(2*PI*t*{vel})':eval=frame{etiqueta_sticker}"
            )
            filtro_partes.append(
                f"{capa_actual}{etiqueta_sticker}overlay=x='{sticker['x']}':y={sticker['y']}{etiqueta_salida}"
            )
            capa_actual = etiqueta_salida

        filtro_completo = ";".join(filtro_partes)

        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", f"{carpeta}/escena_{i}.jpg"] + inputs_extra + [
            "-filter_complex", filtro_completo,
            "-map", "[vout]",
            "-t", str(dur_clip), "-pix_fmt", "yuv420p", clip_out
        ]
        subprocess.run(cmd, check=True)
    else:
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
        punto = offset - transicion
        puntos_transicion.append(punto)
        filtro += f"{salida_actual}[{i}:v]xfade=transition={transicion_tipo}:duration={transicion}:offset={punto}{etiqueta_salida};"
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
    "-i", f"{carpeta}/lista_audio.txt",
    f"{carpeta}/narracion_completa.wav"
], check=True)

musica_path = f"{carpeta}/musica.mp3"
if os.path.exists(musica_path):
    subprocess.run([
        "ffmpeg", "-y",
        "-i", f"{carpeta}/narracion_completa.wav",
        "-i", musica_path,
        "-filter_complex",
        "[0:a]volume=1.56[narracion_alta];[1:a]volume=0.234[musica_alta];"
        "[narracion_alta][musica_alta]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[audio_final]",
        "-map", "[audio_final]",
        f"{carpeta}/audio_final.wav"
    ], check=True)
else:
    subprocess.run(["cp", f"{carpeta}/narracion_completa.wav", f"{carpeta}/audio_final.wav"], check=True)

efecto_elegido = random.choice(EFECTOS_TRANSICION) if os.path.exists(EFECTOS_TRANSICION[0]) else None

if efecto_elegido and puntos_transicion:
    inputs_efectos = []
    for _ in puntos_transicion:
        inputs_efectos += ["-i", efecto_elegido]

    filtro_efectos = "[0:a]anull[base];"
    entradas_mezcla = ["[base]"]
    for idx, punto in enumerate(puntos_transicion):
        entrada_num = idx + 1
        delay_ms = int(punto * 1000)
        etiqueta = f"[ef{idx}]"
        filtro_efectos += f"[{entrada_num}:a]adelay={delay_ms}|{delay_ms},volume=0.6{etiqueta};"
        entradas_mezcla.append(etiqueta)

    total_entradas = len(entradas_mezcla)
    filtro_efectos += "".join(entradas_mezcla) + (
        f"amix=inputs={total_entradas}:duration=first:dropout_transition=0:normalize=0[mezcla_efectos];"
        f"[mezcla_efectos]alimiter=limit=0.95[audio_con_efectos]"
    )

    cmd_efectos = ["ffmpeg", "-y", "-i", f"{carpeta}/audio_final.wav"] + inputs_efectos + [
        "-filter_complex", filtro_efectos,
        "-map", "[audio_con_efectos]",
        f"{carpeta}/audio_con_efectos.wav"
    ]
    subprocess.run(cmd_efectos, check=True)
    audio_para_video = f"{carpeta}/audio_con_efectos.wav"
else:
    audio_para_video = f"{carpeta}/audio_final.wav"

# --- Bloque final: especificaciones de Facebook Reels ---
# -level 4.2: subido desde 4.0, porque 1080x1920 a 30fps queda al limite justo
#   del maximo de macrobloques/segundo que permite el Level 4.0, lo cual puede
#   hacer que el procesamiento de Facebook falle silenciosamente
# -r 30: framerate fijo (constante), sin variaciones
# -g 90 -keyint_min 90 -sc_threshold 0: keyframe cada 90 frames (3s a 30fps) de forma
#   fija, dentro del rango 2-5s que pide Facebook, sin detección automática de escena
# -ar 48000 -ac 2: audio a 48kHz estéreo, como pide Facebook
subprocess.run([
    "ffmpeg", "-y",
    "-i", f"{carpeta}/video_mudo.mp4",
    "-i", audio_para_video,
    "-c:v", "libx264", "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p",
    "-r", "30",
    "-g", "90", "-keyint_min", "90", "-sc_threshold", "0",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
    "-movflags", "+faststart",
    "-shortest",
    f"{carpeta}/video_final.mp4"
], check=True)

print("Video final generado correctamente.")
