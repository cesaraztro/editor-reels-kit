"""Detecta líneas finas horizontales fijas quemadas en el crudo (guías de apps de grabación o teleprompter).

  .venv/bin/python lineas_fijas.py <fuente.mp4> <salida.json>   -> {"filas": [0.276, ...]} (posición normalizada)

Una línea fina se distingue del borde de un mueble porque difiere de las filas de ARRIBA y de ABAJO a la vez,
y porque está en la misma fila en todos los momentos del video.
"""
import json, subprocess, sys
import numpy as np

src, out = sys.argv[1], sys.argv[2]
info = subprocess.run(["ffmpeg", "-hide_banner", "-i", src], capture_output=True, text=True).stderr
import re
m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 30
wh = re.search(r", (\d{3,4})x(\d{3,4})", info)
W, H = int(wh[1]), int(wh[2])
votos = {}
tiempos = [dur * f for f in (0.15, 0.35, 0.55, 0.75, 0.9)]
for t in tiempos:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", src, "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    if len(raw) < W * H:
        continue
    a = np.frombuffer(raw, np.uint8).reshape(H, W).astype(float)
    # punteada: mucho contraste horizontal (punto/hueco) comparado con las filas vecinas
    hf = np.abs(np.diff(a, axis=1)).mean(axis=1)
    vec = (np.roll(hf, 3) + np.roll(hf, -3)) / 2
    punteo = hf - vec
    # fina: difiere de arriba Y de abajo (un borde de mueble solo difiere de un lado)
    fina = np.minimum(np.abs(a - np.roll(a, 2, axis=0)).mean(axis=1), np.abs(a - np.roll(a, -2, axis=0)).mean(axis=1))
    cand = np.where((punteo > np.percentile(punteo, 99.6)) & (fina > np.median(fina) * 2))[0]
    for y in cand:
        if not 5 < y < H - 5:
            continue
        # punteada = patrón periódico punto/hueco: un pico claro en el espectro de la fila
        r = a[y] - (a[y - 3] + a[y + 3]) / 2
        esp = np.abs(np.fft.rfft(r - r.mean()))[8:]
        if esp.max() / (esp.mean() + 1e-9) > 6:
            votos[int(y)] = votos.get(int(y), 0) + 1
filas = sorted(y for y, v in votos.items() if v >= len(tiempos) - 1)
grupos = []
for y in filas:
    if grupos and y - grupos[-1][-1] <= 3:
        grupos[-1].append(y)
    else:
        grupos.append([y])
res = [round(sum(g) / len(g) / H, 5) for g in grupos]
# solo se reparan las guías indicadas en estilo.json > lineas_guia (las repisas también son líneas fijas)
guias = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else []
if guias:
    res = [r for r in res if any(abs(r - g) < 0.004 for g in guias)]
json.dump({"filas": res}, open(out, "w"))
print(f"líneas fijas: {[round(r * H) for r in res]} (de {H} px)")
