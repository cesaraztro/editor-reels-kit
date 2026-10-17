#!/usr/bin/env python3
"""Revisión de calidad automática de un reel ya renderizado.

  python3 qa.py <proyecto>        -> <proyecto>/qa/qa.json + hojas de fotogramas

Lee <proyecto>/timeline.json (lo escribe reel.py render) y el mp4 de 03-exportados.
Chequeos duros (bloquean la entrega): cortes a media palabra, pausas largas, repeticiones,
volumen (-14 LUFS ±1.5, pico ≤ -1 dBTP) y que el video final diga lo mismo que el guion.
Avisos: duración fuera de 25–45 s, gancho tardío, choques de gráficos.
"""
import difflib, json, re, subprocess, sys, unicodedata
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
RAIZ = MOTOR.parent
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
try:   # idioma de los videos (marca.json en la raíz del kit); por defecto español
    IDIOMA = json.loads((RAIZ / "marca.json").read_text()).get("idioma", "es")
except Exception:
    IDIOMA = "es"


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9ñ]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def volumen(final):
    err = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(final), "-af", "ebur128=peak=true", "-f", "null", "-"]).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", err)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp else None)


def retranscribir(final, qa_dir):
    wav = qa_dir / "final16k.wav"
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-ac", "1", "-ar", "16000", str(wav)])
    r = sh(["uvx", "--from", "mlx-whisper", "mlx_whisper", str(wav), "--model", WHISPER_MODEL, "--language", IDIOMA,
            "--condition-on-previous-text", "False", "--output-format", "json", "--output-dir", str(qa_dir),
            "--output-name", "final"])
    f = qa_dir / "final.json"
    if r.returncode or not f.exists():
        return None
    return json.loads(f.read_text()).get("text", "")


def repetidas(palabras_txt, n=3):
    ws = [w for w in (norm(x) for x in palabras_txt) if w]
    vistos, out = {}, []
    for k in range(len(ws) - n + 1):
        g = tuple(ws[k:k + n])
        if len("".join(g)) < 10:
            continue
        if g in vistos and k - vistos[g] <= 25:
            out.append(" ".join(g))
        vistos[g] = k
    return out


def hojas(final, tl, qa_dir):
    total = tl["total"]
    # hoja general 4x4
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(final), "-vf",
        f"fps={16 / max(total, 1):.4f},scale=240:-2,tile=8x2:padding=4:color=white", "-frames:v", "1", str(qa_dir / "hoja.jpg")])
    # momentos clave: héroes, entradas/salidas de B-roll, firma, CTA
    claves = []
    for g in tl.get("graficos", []):
        if g["comp"] in ("Heroe", "Firma", "Cierre", "Titulo"):
            claves.append((g["t0"] + min(1.0, g["dur"] * 0.6), g["comp"]))
    for b in tl.get("brolls", []):
        claves += [(b["t0"] + 0.1, "broll in"), (b["t0"] + b["dur"] + 0.1, "broll out")]
    claves = sorted(claves)[:16]
    if claves:
        ins, fc = [], []
        for i, (t, _) in enumerate(claves):
            ins += ["-ss", f"{min(t, total - 0.1):.2f}", "-i", str(final)]
            fc.append(f"[{i}:v]trim=end_frame=1,scale=240:-2[c{i}]")
        cols = min(8, len(claves))
        filas = (len(claves) + cols - 1) // cols
        relleno = cols * filas - len(claves)
        for j in range(relleno):
            fc.append(f"color=white:s=240x426:d=0.04,trim=end_frame=1[z{j}]")
        celdas = "".join(f"[c{i}]" for i in range(len(claves))) + "".join(f"[z{j}]" for j in range(relleno))
        fc.append(f"{celdas}xstack=inputs={cols * filas}:layout=" +
                  "|".join(f"{(k % cols) * 240}_{(k // cols) * 426}" for k in range(cols * filas)) + "[o]")
        sh(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fc), "-map", "[o]", "-frames:v", "1",
            str(qa_dir / "claves.jpg")])
    return [c[1] for c in claves]


def revisar(p, final=None):
    p = Path(p).resolve()
    final = Path(final) if final else RAIZ / "03-exportados" / f"{p.name}.mp4"
    tl = json.loads((p / "timeline.json").read_text())
    qa_dir = p / "qa"
    qa_dir.mkdir(exist_ok=True)
    duros, avisos, datos = [], [], {}

    # 1) cortes: el audio debe estar en silencio justo en cada corte (medido sobre la voz del crudo)
    tol = lambda c: tl["umbral"] + (10 if c["lado"] == "sale" else 6)   # al salir se tolera la cola de una respiración
    malos = [c for c in tl["cortes"] if c["nivel"] > tol(c) and not c.get("deliberado")]
    deliberados = [c for c in tl["cortes"] if c["nivel"] > tol(c) and c.get("deliberado")]
    if deliberados:
        avisos.append("recortes intencionales dentro de una frase: " + ", ".join(f"{c['t']:.1f}s" for c in deliberados[:4]))
    datos["cortes"] = len(tl["cortes"])
    if malos:
        duros.append("cortes a media palabra: " + ", ".join(f"{c['t']:.1f}s({c['lado']} {c['nivel']:.0f}dB)" for c in malos[:6]))
    # 2) pausas que quedaron dentro de la voz
    largas = [x for x in tl["pausas"] if x["dur"] > 0.25]
    datos["pausas_largas"] = len(largas)
    if largas:
        duros.append("pausas > 0.25 s: " + ", ".join(f"{x['t']:.1f}s({x['dur']:.2f})" for x in largas[:6]))
    # 3) repeticiones en el guion final
    reps = repetidas([w["texto"] for w in tl["palabras"]])
    if reps:
        duros.append("frases repetidas en el guion: " + "; ".join(reps[:4]))
    # 4) volumen
    lufs, tp = volumen(final)
    datos["lufs"], datos["pico"] = lufs, tp
    if lufs is None or abs(lufs + 14) > 1.5:
        duros.append(f"volumen {lufs} LUFS (meta -14 ±1.5)")
    if tp is not None and tp > -0.5:
        duros.append(f"pico {tp} dBTP (meta ≤ -1)")
    # 5) lo que realmente suena: re-transcripción del mp4 final contra el guion
    oido = retranscribir(final, qa_dir)
    if oido is not None:
        a = [norm(w["texto"]) for w in tl["palabras"]]
        b = [x for x in (norm(w) for w in oido.split()) if x]
        sim = difflib.SequenceMatcher(None, a, b).ratio()
        datos["similitud_audio_guion"] = round(sim, 3)
        reps_oido = repetidas(oido.split())
        if sim < 0.85:
            duros.append(f"el audio final no coincide con el guion (similitud {sim:.2f})")
        if reps_oido:
            duros.append("se escucha una repetición: " + "; ".join(reps_oido[:3]))
    else:
        avisos.append("no se pudo re-transcribir el video final")
    # avisos editoriales
    total = tl["total"]
    datos["duracion"] = round(total, 1)
    if not 25 <= total <= 46:
        avisos.append(f"duración {total:.1f}s fuera de 25–45 s")
    if tl["palabras"] and tl["palabras"][0]["t0"] > 1.5:
        avisos.append(f"la primera palabra entra en {tl['palabras'][0]['t0']:.1f}s (gancho tardío)")
    g = tl.get("graficos", [])
    for h in [x for x in g if x["comp"] == "Heroe"]:
        for o in g:
            if o is not h and o["comp"] == "Pop" and o["t0"] < h["t0"] + h["dur"] and o["t0"] + o["dur"] > h["t0"]:
                avisos.append(f"un pop se encima con la palabra héroe en {h['t0']:.1f}s")
    sfx = tl.get("sfx", [])
    if total and len(sfx) / total > 0.5:
        avisos.append(f"demasiados efectos de sonido ({len(sfx)} en {total:.0f}s)")
    datos["momentos"] = hojas(final, tl, qa_dir)
    res = {"estado": "ok" if not duros else "falla", "duros": duros, "avisos": avisos, "datos": datos,
           "hojas": [str(qa_dir / "hoja.jpg"), str(qa_dir / "claves.jpg")]}
    (qa_dir / "qa.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return res


if __name__ == "__main__":
    r = revisar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    sys.exit(0 if r["estado"] == "ok" else 1)
