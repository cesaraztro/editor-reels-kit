#!/usr/bin/env python3
"""Detecta cuándo la persona mira fuera de cámara (leyendo el guion) y la posición de la cabeza.

  .venv/bin/python mirada.py <fuente.mp4> <salida.json>

Salida: {"fps":10, "cuadros":[[t, desviacion, x, y, escala], ...], "fuera":[[t0,t1], ...]}
Calibración automática: la mediana de todo el video es "mirando a cámara".
"""
import json, subprocess, sys
from pathlib import Path
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode

FPS, W, H = 10, 360, 640
UMBRAL = 3.5  # desviaciones (MAD) respecto a la mirada típica
MODELO = Path(__file__).parent / "modelos" / "face_landmarker.task"


def iris(lm, centro, a, b, arriba, abajo):
    c = np.array([lm[centro].x, lm[centro].y])
    p, q = np.array([lm[a].x, lm[a].y]), np.array([lm[b].x, lm[b].y])
    h = np.dot(c - p, q - p) / max(np.dot(q - p, q - p), 1e-6)
    v = (c[1] - lm[arriba].y) / max(lm[abajo].y - lm[arriba].y, 1e-6)
    return h, v


def main(src, out):
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", src, "-vf", f"fps={FPS},scale={W}:{H}",
                             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    det = FaceLandmarker.create_from_options(FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MODELO)), running_mode=RunningMode.VIDEO,
        num_faces=1, output_facial_transformation_matrixes=True))
    filas, k = [], 0
    while True:
        buf = proc.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.frombuffer(buf, np.uint8).reshape(H, W, 3))
        r = det.detect_for_video(img, int(k * 1000 / FPS))
        t = k / FPS; k += 1
        if not r.face_landmarks:
            filas.append([t, None]); continue
        lm = r.face_landmarks[0]
        m = np.array(r.facial_transformation_matrixes[0])
        yaw = np.degrees(np.arctan2(-m[2, 0], np.hypot(m[2, 1], m[2, 2])))
        pitch = np.degrees(np.arctan2(m[2, 1], m[2, 2]))
        h1, v1 = iris(lm, 468, 33, 133, 159, 145)
        h2, v2 = iris(lm, 473, 362, 263, 386, 374)
        xs = [p.x for p in lm]; ys = [p.y for p in lm]
        filas.append([t, [yaw, pitch, (h1 + h2) / 2, (v1 + v2) / 2], lm[1].x, lm[1].y, max(ys) - min(ys)])

    validas = np.array([f[1] for f in filas if f[1] is not None])
    med = np.median(validas, axis=0)
    mad = np.median(np.abs(validas - med), axis=0) * 1.4826 + np.array([1.5, 1.5, 0.02, 0.03])
    cuadros = []
    for f in filas:
        if f[1] is None:
            cuadros.append([round(f[0], 2), 99, None, None, None]); continue
        z = np.abs((np.array(f[1]) - med) / mad)
        cuadros.append([round(f[0], 2), round(float(z.max()), 1), round(f[2], 4), round(f[3], 4), round(f[4], 4)])
    # intervalos fuera >= 0.3 s (tolerando 1 cuadro de ruido)
    fuera, ini = [], None
    marcas = [int(c[1] > UMBRAL) for c in cuadros]
    for i, v in enumerate(marcas + [0]):
        if v and ini is None:
            ini = i
        elif not v and ini is not None:
            if i + 1 < len(marcas) and marcas[i + 1]:
                continue
            if (i - ini) / FPS >= 0.3:
                fuera.append([round(ini / FPS, 2), round(i / FPS, 2)])
            ini = None
    Path(out).write_text(json.dumps({"fps": FPS, "cuadros": cuadros, "fuera": fuera}))
    print(f"mirada: {len(cuadros)} cuadros, {len(fuera)} tramos fuera de cámara")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
