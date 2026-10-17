#!/usr/bin/env python3
"""Motor de reels premium (editor-reels-kit): rápido, local y de bajo costo.

  reel.py preparar <video> [--slug nombre]   -> proyecto + transcripcion.txt + edicion.json
  reel.py lote                               -> prepara todo lo nuevo de 01-crudos
  reel.py render <carpeta_proyecto>          -> 03-exportados/<proyecto>.mp4 + copy + portada + QA

El agente solo lee transcripcion.txt (y broll/catalogo.txt) y escribe edicion.json.
Render: gráficos con alfa en Remotion (solo su duración, con caché) + UNA pasada de ffmpeg.
"""
import os, argparse, array, bisect, datetime, hashlib, json, math, re, shutil, subprocess, sys, time, unicodedata, wave
from pathlib import Path

MOTOR = Path(__file__).resolve().parent
RAIZ = MOTOR.parent
PROYECTOS, EXPORTADOS = RAIZ / "02-proyectos", RAIZ / "03-exportados"
ENTREGADOS = RAIZ / "Entregados"
REC = RAIZ / "04-recursos"
MUSICA, SFX, BROLL = REC / "musica", REC / "sfx", REC / "broll"
FUENTES = MOTOR / "fuentes"
# Archivos pesados (copia 4K, máscara, bloques, gráficos ProRes) fuera de carpetas sincronizadas (iCloud, Dropbox…):
# subir cientos de MB a mitad del render lo hace 5–10× más lento. Cambia la ruta con la variable REELS_CACHE.
LOCAL = Path(os.environ.get("REELS_CACHE") or (Path.home() / "Movies" / "editor-reels-cache")).expanduser()
CACHE = LOCAL / "cache"


def pesado(p, nombre):
    """Ruta local (sin iCloud) para un archivo pesado del proyecto; respeta el que ya exista en el proyecto."""
    viejo = p / nombre
    if viejo.exists():
        return viejo
    d = LOCAL / p.name
    d.mkdir(parents=True, exist_ok=True)
    return d / nombre
VENV_PY = MOTOR / ".venv" / "bin" / "python"
FPS, W, H = 30, 1080, 1920
EST = json.loads((MOTOR / "estilo.json").read_text())

# ---------------------------------------------------------------- marca (marca.json en la raíz del kit)
MARCA_DEF = {
    "nombre": "Tu Nombre", "rol": "Fundador · TuMarca", "empresa": "TuMarca", "mostrar_firma": True,
    "eyebrow": "TuMarca", "cta_texto": "Comenta la palabra", "idioma": "es", "vocabulario": "", "correcciones": {},
    "colores": {"fondo": "#14142B", "papel": "#F5F5F7", "acento": "#7DD3FC", "oro": "#FF8A3D"},
    "logo": "logo/tu-logo.svg",
    "fuentes": {"titulo": "Cinzel", "cuerpo": "Poppins", "subtitulos": "Poppins SemiBold"},
}


def _hex(c, defecto):
    c = str(c or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", c):
        c = "#" + "".join(ch * 2 for ch in c[1:])
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", c):
        print(f"  (color inválido en marca.json: {c!r}; uso {defecto})")
        return defecto
    return c.upper()


def cargar_marca():
    m = json.loads(json.dumps(MARCA_DEF))
    f = RAIZ / "marca.json"
    if f.exists():
        usr = json.loads(f.read_text())
        for k, v in usr.items():
            if k.startswith("_"):
                continue
            if isinstance(v, dict) and isinstance(m.get(k), dict) and k != "correcciones":
                m[k].update(v)
            else:
                m[k] = v
    else:
        print("  (no hay marca.json en la raíz del kit: uso la marca genérica)")
    m["colores"] = {k: _hex(m["colores"].get(k), MARCA_DEF["colores"][k]) for k in MARCA_DEF["colores"]}
    return m


MARCA = cargar_marca()


def logo_data_uri():
    """El logo de marca.json como data URI para que Remotion lo dibuje sin rutas (SVG o PNG/JPG/WEBP)."""
    import base64, mimetypes
    for cand in (MARCA.get("logo"), MARCA_DEF["logo"]):
        if not cand:
            continue
        ruta = Path(cand).expanduser()
        ruta = ruta if ruta.is_absolute() else RAIZ / ruta
        if ruta.is_file():
            mime = "image/svg+xml" if ruta.suffix.lower() == ".svg" else (mimetypes.guess_type(ruta.name)[0] or "image/png")
            if ruta.stat().st_size > 600_000:
                print(f"  (el logo pesa {ruta.stat().st_size // 1000} KB: usa un SVG o un PNG pequeño)")
            return f"data:{mime};base64," + base64.b64encode(ruta.read_bytes()).decode()
    return ""


def marca_props(con_logo=False):
    """Lo que Remotion necesita de la marca (colores, fuentes y, si hace falta, el logo)."""
    pr = {"colores": MARCA["colores"],
          "fuentes": {"titulo": MARCA["fuentes"]["titulo"], "cuerpo": MARCA["fuentes"]["cuerpo"]}}
    if con_logo:
        pr["logo"] = logo_data_uri()
    return pr


# el tipo de letra de los subtítulos (ASS) sale de marca.json; hay que copiar el .ttf a _motor/fuentes/ si no está instalada
EST["subtitulos"]["fuente"] = MARCA["fuentes"].get("subtitulos") or EST["subtitulos"]["fuente"]
EST["subtitulos"]["fuente_chica"] = MARCA["fuentes"].get("subtitulos_chica") or EST["subtitulos"]["fuente"]

GAP_CORTE = 0.30            # silencio entre palabras que se elimina (s)
PRE, POST = 0.04, 0.14
MIRADA_OK = 1.3             # desviación de mirada aceptable (ver mirada.py)
WHISPER_MODEL = "mlx-community/whisper-large-v3-turbo"
# pista para Whisper: muletillas y vocabulario propio (nombre de la marca y términos de tu tema)
PROMPT = ("Eh, este, mmm, o sea... " + ", ".join(x for x in (MARCA["empresa"], MARCA.get("vocabulario")) if x) + ".")
TONEMAP = ("zscale=tin=arib-std-b67:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=203,format=gbrpf32le,"
           "zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv")


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"ERROR en {Path(str(cmd[0])).name}:\n{r.stderr[-3000:]}")
    return r


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "reel"


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s)


def info(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    dur = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else 0
    v = re.search(r"Video:.*?(\d{3,5})x(\d{3,5})", err)
    w, h = (int(v[1]), int(v[2])) if v else (0, 0)
    rot = re.search(r"rotation of (-?[\d.]+)", err)
    if rot and abs(float(rot[1])) % 180 == 90:
        w, h = h, w
    return {"dur": dur, "w": w, "h": h, "hdr": bool(re.search(r"arib-std-b67|smpte2084", err))}


def q(t):
    return round(t * FPS) / FPS


# ---------------------------------------------------------------- mirada
class Mirada:
    def __init__(self, p):
        self._p = p
        f = p / "mirada.json"
        self.c = json.loads(f.read_text())["cuadros"] if f.exists() else []
        s = [x[1] for x in self.c]
        # mediana de 3 para quitar parpadeos
        self.s = [sorted(s[max(0, i - 1):i + 2])[len(s[max(0, i - 1):i + 2]) // 2] for i in range(len(s))]

    def ok(self, t):
        i = int(round(t * 10))
        return not self.c or (0 <= i < len(self.s) and self.s[i] <= MIRADA_OK)

    def regreso(self, t, maximo=1.0):
        """Primer instante >= t con mirada en cámara sostenida 0.3 s."""
        k = 0.0
        while k <= maximo:
            if all(self.ok(t + k + j * 0.1) for j in range(3)):
                return k
            k += 0.1
        return maximo

    def cola(self, t, maximo=0.6):
        """Cuánto tiempo después de t sigue mirando a cámara."""
        k = 0.0
        while k < maximo and self.ok(t + k + 0.1):
            k += 0.1
        return k

    def fuera(self, a, b):
        """Tramos (>=0.3 s) fuera de cámara dentro de [a,b]."""
        out, ini, t = [], None, a
        while t <= b:
            if not self.ok(t):
                ini = t if ini is None else ini
            elif ini is not None:
                if t - ini >= 0.3:
                    out.append((ini, t))
                ini = None
            t += 0.1
        if ini is not None and b - ini >= 0.3:
            out.append((ini, b))
        return out

    def cara(self, a, b):
        pts = [(x[2], x[3]) for x in self.c if a <= x[0] <= b and x[2] is not None]
        if not pts:
            return 0.5, 0.4
        return sorted(p[0] for p in pts)[len(pts) // 2], sorted(p[1] for p in pts)[len(pts) // 2]


# ---------------------------------------------------------------- preparar
class Energia:
    """Nivel de la voz cada 10 ms (voz16k.wav) para que los cortes caigan en silencio real y no a media palabra."""
    def __init__(self, wav):
        w = wave.open(str(wav))
        data = array.array("h", w.readframes(w.getnframes()))
        hop = w.getframerate() // 100
        self.db = [10 * math.log10(sum(x * x for x in data[i:i + hop]) / hop / 1073741824 + 1e-12)
                   for i in range(0, len(data) - hop, hop)]
        srt = sorted(self.db)
        piso, voz = srt[len(srt) // 10], srt[int(len(srt) * 0.9)]
        self.umbral = max(piso + 8, voz - 26)
        self.fuerte = voz - 10   # voz clara (no ruido de silla, respiración ni roce)

    def arranque_real(self, t0, t1):
        """Primera voz clara dentro de [t0, t1]; None si la palabra arranca de inmediato."""
        x = t0
        while x < t1:
            if all(self.nivel(x + k * 0.01) >= self.fuerte for k in range(3)):
                return x if x - t0 > 0.3 else None
            x = round(x + 0.01, 2)
        return None

    def nivel(self, t):
        i = int(round(t * 100))
        return self.db[i] if 0 <= i < len(self.db) else -120

    def quieto(self, a, b):
        return all(self.nivel(a + k * 0.01) < self.umbral for k in range(int(round((b - a) * 100)) + 1))

    def inicio(self, t, limite):
        """Retrocede desde t hasta el silencio anterior (sin pasar 'limite')."""
        x = t
        while x - 0.06 >= limite:
            if self.quieto(x - 0.06, x):
                return x
            x -= 0.01
        cands = [limite + i * 0.01 for i in range(int((t - limite) * 100) + 1)]
        return min(cands, key=self.nivel) if cands else t

    def fin(self, t, limite):
        """Avanza desde t hasta el silencio siguiente (sin pasar 'limite')."""
        x = t
        while x + 0.08 <= limite:
            if self.quieto(x, x + 0.08):
                return x
            x += 0.01
        cands = [t + i * 0.01 for i in range(int((limite - t) * 100) + 1)]
        return min(cands, key=self.nivel) if cands else t


def preparar(a):
    src = Path(a.video).expanduser().resolve()
    if not src.exists():
        sys.exit(f"No existe {src}")
    nombre = f"{datetime.date.today():%Y-%m-%d}_{slugify(a.slug or src.stem)}"
    p = PROYECTOS / nombre
    p.mkdir(parents=True, exist_ok=True)
    (p / "origen.txt").write_text(str(src))
    i = info(src)
    print(f"Fuente: {i['w']}x{i['h']} {i['dur']:.1f}s HDR={i['hdr']}")

    fuente = p / "fuente.mp4"
    if not fuente.exists():
        vf = [f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H}"]
        if i["hdr"]:
            vf.append(TONEMAP)
        vf.append("format=yuv420p")
        sh(["ffmpeg", "-y", "-hwaccel", "videotoolbox", "-i", str(src), "-map", "0:v:0", "-map", "0:a:0",
            "-vf", ",".join(vf), "-r", str(FPS), "-c:v", "h264_videotoolbox", "-b:v", "16M",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-colorspace", "bt709", str(fuente)])
    wav = p / "voz16k.wav"
    if not wav.exists():
        sh(["ffmpeg", "-y", "-i", str(fuente), "-ac", "1", "-ar", "16000", str(wav)])
    # Whisper y mirada en paralelo
    procs = []
    if not (p / "transcripcion.json").exists():
        procs.append(subprocess.Popen(
            ["uvx", "--from", "mlx-whisper", "mlx_whisper", str(wav), "--model", WHISPER_MODEL, "--language", MARCA["idioma"],
             "--word-timestamps", "True", "--condition-on-previous-text", "False",
             "--hallucination-silence-threshold", "2", "--initial-prompt", PROMPT, "--output-format", "json",
             "--output-dir", str(p), "--output-name", "transcripcion"],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True))
    if not (p / "caras.json").exists() and (MOTOR / "bin" / "caras").exists():
        procs.append(subprocess.Popen([str(MOTOR / "bin" / "caras"), str(fuente), str(p / "caras.json")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True))
    if not (p / "lineas_fijas.json").exists() and VENV_PY.exists() and EST.get("lineas_guia"):
        procs.append(subprocess.Popen([str(VENV_PY), str(MOTOR / "lineas_fijas.py"), str(fuente), str(p / "lineas_fijas.json"),
                                       ",".join(str(x) for x in EST["lineas_guia"])],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True))
    if not (p / "mirada.json").exists() and VENV_PY.exists():
        procs.append(subprocess.Popen([str(VENV_PY), str(MOTOR / "mirada.py"), str(fuente), str(p / "mirada.json")],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True))
    for pr in procs:
        _, err = pr.communicate()
        if pr.returncode:
            sys.exit(err[-2000:])

    lineas = construir_lineas(json.loads((p / "transcripcion.json").read_text()), i["dur"])
    mir = Mirada(p)
    for l in lineas:
        l["lee"] = mir.regreso(l["t0"]) > 0.25 or bool(mir.fuera(l["t0"] + 0.3, l["t1"]))
    (p / "lineas.json").write_text(json.dumps(lineas, ensure_ascii=False))
    escribir_txt(p, lineas, i["dur"])
    ed = p / "edicion.json"
    if not ed.exists():
        ed.write_text(json.dumps({"gancho": "", "eyebrow": "", "lineas": [l["id"] for l in lineas],
                                  "correcciones": MARCA["correcciones"], "enfasis": [], "tarjetas": [],
                                  "broll": [], "cta": None, "musica": "auto",
                                  "copy": {"titulo": "", "caption": "", "hashtags": []}}, ensure_ascii=False, indent=2))
    lanzar_precalentar(p)
    print(f"\nProyecto: {p}\nLee: transcripcion.txt · Edita: edicion.json")


def lanzar_precalentar(p):
    """Copia 4K + máscara completa en segundo plano mientras se escribe edicion.json (el render ya no las espera)."""
    if pesado(p, "fuente_hd.mp4").exists() and pesado(p, "matte.mp4").exists():
        return
    log = open(p / "precalentar.log", "w")
    pr = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "precalentar", str(p)],
                          stdout=log, stderr=log, start_new_session=True)
    (p / "precalentar.lock").write_text(str(pr.pid))


def precalentar(a):
    p = Path(a.proyecto).expanduser().resolve()
    t0 = time.time()
    try:
        dur = info(p / "fuente.mp4")["dur"]
        pr = lanzar_matte(p, [{"s0": 0.0, "s1": dur}])   # Apple Vision y la copia 4K corren a la vez
        fuente_hd(p)
        esperar_matte(pr)
        print(f"precalentado en {time.time() - t0:.0f}s")
    finally:
        (p / "precalentar.lock").unlink(missing_ok=True)


def esperar_precalentar(p):
    lock = p / "precalentar.lock"
    if not lock.exists():
        return
    try:
        os.kill(int(lock.read_text().strip()), 0)
    except (OSError, ValueError):
        lock.unlink(missing_ok=True); return
    print("  esperando la copia 4K y la máscara (precalentar)…", flush=True)
    while lock.exists():
        time.sleep(1)


def construir_lineas(tj, dur):
    words = []
    for seg in tj.get("segments", []):
        for w in seg.get("words", []):
            t = w["word"].strip()
            if t and w["end"] > w["start"] and w["start"] < dur - 0.05:
                words.append({"w": t, "t0": round(w["start"], 3), "t1": round(min(w["end"], dur), 3)})
    words.sort(key=lambda x: x["t0"])
    limpio = []
    for w in words:
        if limpio and abs(w["t0"] - limpio[-1]["t0"]) < 0.02 and w["w"] == limpio[-1]["w"]:
            continue
        limpio.append(w)
    grupos, actual = [], []
    for w in limpio:
        if actual and w["t0"] - actual[-1]["t1"] > 1.2:
            grupos.append(actual); actual = []
        actual.append(w)
        if re.search(r"[.?!…]$", w["w"]):
            grupos.append(actual); actual = []
    if actual:
        grupos.append(actual)
    out = []
    for ws in grupos:
        if ws[-1]["t1"] - ws[0]["t0"] < 0.25:
            continue
        out.append({"id": f"L{len(out)+1:02d}", "t0": ws[0]["t0"], "t1": ws[-1]["t1"],
                    "texto": " ".join(x["w"] for x in ws), "palabras": ws})
    return out


def dur_max(w):
    """Duración máxima creíble de una palabra. Si Whisper le asigna más, casi siempre se tragó una toma repetida."""
    letras = len(re.sub(r"\W", "", w["w"]))
    digitos = len(re.sub(r"\D", "", w["w"]))
    if digitos:  # "14" se dice "catorce": se mide como palabra hablada
        letras = max(letras, digitos * 4 + 2)
    return max(0.6, 0.11 * letras + 0.4)


def inflada(w, primera=False):
    # la primera palabra de una línea suele venir estirada hacia el silencio previo: margen extra
    return w["t1"] - w["t0"] > dur_max(w) + (0.6 if primera else 0)


def sospechosas(l):
    return [w for i, w in enumerate(l["palabras"]) if inflada(w, i == 0)]


def escribir_txt(p, lineas, dur):
    txt = [f"# {p.name} · {dur:.0f}s · {len(lineas)} líneas",
           "# ID inicio-fin | texto. Repeticiones = tomas (quédate con la mejor). 👀 = se nota que lee. "
           "⚠️ = Whisper se tragó audio (casi siempre una toma repetida): el motor la recorta solo, pero revisa que la frase siga completa."]
    for l in lineas:
        sus = sospechosas(l)
        aviso = "".join(f" ⚠️[{w['w']} {w['t1'] - w['t0']:.1f}s]" for w in sus)
        txt.append(f"{l['id']} {l['t0']:.1f}-{l['t1']:.1f} |{' 👀' if l.get('lee') else ''} {l['texto']}{aviso}")
    (p / "transcripcion.txt").write_text("\n".join(txt) + "\n")


def repeticiones(palabras, ventana=10.0):
    """Frases de 3+ palabras que aparecen dos veces cerca en el reel final (tomas repetidas que se colaron)."""
    n_ = [norm(w["texto"]) for w in palabras]
    vistas, out = {}, []
    for k in range(len(n_) - 2):
        clave = tuple(n_[k:k + 3])
        if len("".join(clave)) < 10:
            continue
        if clave in vistas and palabras[k]["t0"] - vistas[clave] < ventana:
            out.append((round(vistas[clave], 1), " ".join(w["texto"] for w in palabras[k:k + 3])))
        vistas[clave] = palabras[k]["t0"]
    return out


def lote(a):
    hechos = {x.read_text().strip() for x in PROYECTOS.glob("*/origen.txt")}
    vids = [v for v in sorted((RAIZ / "01-crudos").iterdir())
            if v.is_file() and v.suffix.lower() in {".mov", ".mp4", ".m4v"} and str(v.resolve()) not in hechos]
    print(f"{len(vids)} video(s) nuevos")
    for v in vids:
        print(f"\n== {v.name}"); preparar(argparse.Namespace(video=str(v), slug=None))


# ---------------------------------------------------------------- render
def parse_ref(ref):
    m = re.fullmatch(r"(L\d+)(?:\[(-?\d*):(-?\d*)\])?", ref.strip())
    if not m:
        sys.exit(f"Referencia inválida en edicion.json: {ref}")
    return m[1], slice(int(m[2]) if m[2] else None, int(m[3]) if m[3] else None)


def ass_color(hexrgb, alpha=0):
    r, g, b = hexrgb[1:3], hexrgb[3:5], hexrgb[5:7]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_t(t):
    cs = int(round(t * 100))
    return f"{cs//360000}:{cs//6000%60:02d}:{cs//100%60:02d}.{cs%100:02d}"


def escribir_ass(palabras, paginas, ruta):
    st = EST["subtitulos"]
    caja = ass_color(MARCA["colores"]["fondo"], st.get("caja_alfa", 0x5A))   # &HAABBGGRR
    blanco, oro = "&H00FFFFFF", ass_color(MARCA["colores"]["oro"])
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{st['fuente']},{st['tam']},{blanco},{blanco},{caja},{caja},0,0,0,0,100,100,0,0,3,{st.get('relleno', 14)},0,2,80,80,{H - st['y']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for pg in paginas:
        idx = pg["palabras"]
        for j, k in enumerate(idx):
            t0 = pg["t0"] if j == 0 else palabras[k]["t0"]
            t1 = palabras[idx[j + 1]]["t0"] if j + 1 < len(idx) else pg["t1"]
            if t1 - t0 < 0.01:
                continue
            partes = []
            for kk in idx:
                w = palabras[kk]
                col = oro if w["enfasis"] else blanco
                alfa = "&H00&" if kk <= k else "&H45&"
                partes.append(f"{{\\1c{col}\\1a{alfa}}}{w['texto']}")
            fad = "{\\fad(140,0)}" if j == 0 else ""
            ev.append(f"Dialogue: 0,{ass_t(t0)},{ass_t(t1)},Sub,,0,0,0,,{fad}{' '.join(partes)}")
    Path(ruta).write_text(head + "\n".join(ev) + "\n")


# ---------- estilo editor: B-roll de Pexels por palabra clave ----------
def pexels_key():
    if os.environ.get("PEXELS_API_KEY"):
        return os.environ["PEXELS_API_KEY"]
    for env in (RAIZ / ".env", MOTOR / ".env"):
        if env.exists():
            for l in env.read_text().splitlines():
                if l.startswith("PEXELS_API_KEY="):
                    return l.split("=", 1)[1].strip().strip('"\'') or None
    return None


def pexels_clip(buscar, dur, usados):
    """Busca un video vertical en Pexels, lo descarga una vez a 04-recursos/broll/pexels/ y lo registra en catalogo.json."""
    import urllib.request, urllib.parse
    carpeta = BROLL / "pexels"
    carpeta.mkdir(parents=True, exist_ok=True)
    cache_f = carpeta / "busquedas.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    if buscar not in cache:
        key = pexels_key()
        if not key:
            print("  (sin PEXELS_API_KEY en .env: se omite el B-roll)"); return None
        url = "https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
            {"query": buscar, "orientation": "portrait", "size": "medium", "per_page": 12})
        req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "editor-reels-kit"})
        vids = json.loads(urllib.request.urlopen(req, timeout=20).read())["videos"]
        cache[buscar] = [{"id": v["id"], "dur": v["duration"], "url": v["url"],
                          "files": [{"w": f["width"], "h": f["height"], "link": f["link"]} for f in v["video_files"]
                                    if f.get("width") and f.get("height") and f["height"] > f["width"]]} for v in vids]
        cache_f.write_text(json.dumps(cache))
    ops = [v for v in cache[buscar] if v["files"] and v["dur"] >= dur + 0.5 and v["id"] not in usados]
    if not ops:
        ops = [v for v in cache[buscar] if v["files"] and v["id"] not in usados]
    if not ops:
        return None
    v = ops[0]
    usados.add(v["id"])
    destino = carpeta / f"{v['id']}.mp4"
    if not destino.exists():
        f = min(v["files"], key=lambda f: (f["h"] < 1280, abs(f["h"] - 1920)))
        tmp = destino.with_suffix(".part")
        sh(["curl", "-sSfL", "-A", "Mozilla/5.0 (editor-reels-kit)", "-o", str(tmp), f["link"]])
        tmp.rename(destino)
        cat_f = BROLL / "catalogo.json"
        cat = json.loads(cat_f.read_text()) if cat_f.exists() else []
        cat.append({"id": f"pexels-{v['id']}", "archivo": f"pexels/{v['id']}.mp4", "tema": buscar, "desc": v["url"],
                    "dur": v["dur"], "fuente": "Pexels (licencia libre)"})
        cat_f.write_text(json.dumps(cat, ensure_ascii=False, indent=1))
    return {"archivo": f"pexels/{v['id']}.mp4", "id": v["id"]}


def buscar_palabra(palabras, texto, lid=None, desde=0.0):
    """Tiempo (en la salida) de la primera aparición de 'texto' (una o más palabras), opcionalmente dentro de una línea."""
    obj = [norm(x) for x in texto.split()]
    for k in range(len(palabras) - len(obj) + 1):
        if palabras[k]["t0"] < desde or (lid and palabras[k]["lid"] != lid):
            continue
        if [norm(palabras[k + j]["texto"]) for j in range(len(obj))] == obj:
            return palabras[k]["t0"], palabras[k + len(obj) - 1]["t1"]
    for k in range(len(palabras)):  # prefijo (p. ej. "automatiz" -> "automatizar")
        if (not lid or palabras[k]["lid"] == lid) and palabras[k]["t0"] >= desde and norm(palabras[k]["texto"]).startswith(obj[0]):
            return palabras[k]["t0"], palabras[k]["t1"]
    return None


# ---------- estilo editor: subtítulos de 1–3 palabras con la palabra clave grande ----------
def paginas_editor(palabras, total):
    st = EST["subtitulos"]
    paginas, cur = [], []
    for k, w in enumerate(palabras):
        cur.append(k)
        txt = " ".join(palabras[j]["texto"] for j in cur)
        nxt = palabras[k + 1] if k + 1 < len(palabras) else None
        if (len(cur) >= st["max_palabras"] or len(txt) >= st["max_chars"] or re.search(r"[.,?!:;…]$", w["texto"])
                or w["enfasis"] or nxt is None or nxt["pieza"] != w["pieza"] or nxt["t0"] - w["t1"] > 0.25
                or (nxt["enfasis"] and len(cur) >= 2)):
            paginas.append(cur); cur = []
    pags = []
    for k, idx in enumerate(paginas):
        fin = palabras[idx[-1]]["t1"] + 0.25
        if k + 1 < len(paginas):
            fin = min(fin, palabras[paginas[k + 1][0]]["t0"])
        pags.append({"t0": palabras[idx[0]]["t0"], "t1": min(fin, total), "palabras": idx})
    return pags


def escribir_ass_editor(palabras, paginas, ruta, extra):
    st = EST["subtitulos"]
    blanco, oro = "&H00FFFFFF", ass_color(MARCA["colores"]["oro"])
    y = st["y"]
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{st['fuente']},{st['tam']},{blanco},{blanco},&H64000000,&H8C000000,0,0,0,0,100,100,0,0,1,2.5,4,5,60,60,0,1
Style: Top,{st['fuente']},{st.get('tam_titulo', 70)},{blanco},{blanco},&H50000000,&H8C000000,0,0,0,0,100,100,0,0,1,3,4,8,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    chica, grande = st.get("tam_chica", 50), st.get("tam_clave", 118)
    f_chica = st.get("fuente_chica", st["fuente"])
    cta, cta_lid = norm(extra.get("cta") or ""), extra.get("cta_lid")
    es_cta = lambda k: bool(cta) and palabras[k]["lid"] == cta_lid and norm(palabras[k]["texto"]) == cta
    ev = []
    for pg in paginas:
        idx = pg["palabras"]
        clave = next((k for k in idx if es_cta(k)), None)
        if clave is None:
            clave = max((k for k in idx if palabras[k]["enfasis"]), key=lambda k: len(palabras[k]["texto"]), default=None)
        for j, k in enumerate(idx):
            t0 = pg["t0"] if j == 0 else palabras[k]["t0"]
            t1 = palabras[idx[j + 1]]["t0"] if j + 1 < len(idx) else pg["t1"]
            if t1 - t0 < 0.01:
                continue

            def pal(kk, extra_tags=""):
                txt = palabras[kk]["texto"]
                vis = "" if kk <= k else "\\alpha&HFF&"
                return f"{{{vis}{extra_tags}}}{txt}{{\\alpha&H00&}}"
            pop = "\\fscx86\\fscy86\\t(0,90,\\fscx100\\fscy100)" if j == 0 else ""
            if clave is None:
                cuerpo = " ".join(pal(kk) for kk in idx)
                ev.append(f"Dialogue: 2,{ass_t(t0)},{ass_t(t1)},Sub,,0,0,0,,{{\\an5\\pos(540,{y}){pop}}}{cuerpo}")
                continue
            antes = [kk for kk in idx if kk < clave]
            despues = [kk for kk in idx if kk > clave]
            ct = re.sub(r"[.,?!:;…]+$", "", palabras[clave]["texto"])
            ct = ct.upper() if len(ct) <= 12 else ct
            if es_cta(clave):
                ct = f"“{ct.upper()}”"
            punch = "\\fscx135\\fscy135\\t(0,110,\\fscx100\\fscy100)" if k == clave else ""
            vis = "" if clave <= k else "\\alpha&HFF&"
            lineas = []
            if antes:
                lineas.append(f"{{\\fn{f_chica}\\fs{chica}\\1c{blanco}}}" + " ".join(pal(kk) for kk in antes))
            fs_c = int(grande * min(1.0, 9.0 / max(1, len(ct))))
            lineas.append(f"{{\\fn{st['fuente']}\\fs{fs_c}\\1c{oro}\\bord3\\shad5{vis}{punch}}}{ct}{{\\alpha&H00&\\fscx100\\fscy100}}")
            if despues:
                lineas.append(f"{{\\fn{f_chica}\\fs{chica}\\1c{blanco}\\bord2.5\\shad4}}" + " ".join(pal(kk) for kk in despues))
            ev.append(f"Dialogue: 2,{ass_t(t0)},{ass_t(t1)},Sub,,0,0,0,,{{\\an5\\pos(540,{y}){pop}}}" + "\\N".join(lineas))
    # título fijo arriba ("línea blanca | línea dorada") con brillo
    tit, total = extra.get("titulo"), extra["total"]
    if tit:
        a, _, b = tit.partition("|")
        txt = a.strip() + (f"\\N{{\\1c{oro}}}{b.strip()}" if b else "")
        t0 = extra.get("titulo_desde", 0.0)
        ev.append(f"Dialogue: 0,{ass_t(t0)},{ass_t(total)},Top,,0,0,0,,{{\\an8\\pos(540,190)\\bord10\\blur14\\3c{oro}\\3a&HA0&\\1a&HFF&\\shad0\\fad(200,0)}}{txt}")
        ev.append(f"Dialogue: 1,{ass_t(t0)},{ass_t(total)},Top,,0,0,0,,{{\\an8\\pos(540,190)\\fad(200,0)}}{txt}")
    # plantilla de lista: barra negra con título + número grande que avanza
    lista = extra.get("lista")
    if lista:
        ev.append(f"Dialogue: 0,{ass_t(0)},{ass_t(total)},Top,,0,0,0,,{{\\an7\\pos(0,0)\\p1\\1c&H000000&\\bord0\\shad0}}m 0 0 l {W} 0 l {W} 300 l 0 300{{\\p0}}")
        ev.append(f"Dialogue: 1,{ass_t(0)},{ass_t(total)},Top,,0,0,0,,{{\\an2\\pos(540,270)\\fs62\\bord0\\shad0}}{lista['titulo'].upper()}")
        marcas = lista["marcas"]
        for i, (t0, num) in enumerate(marcas):
            t1 = marcas[i + 1][0] if i + 1 < len(marcas) else total
            ev.append(f"Dialogue: 1,{ass_t(t0)},{ass_t(t1)},Top,,0,0,0,,{{\\an9\\pos(1020,315)\\fs210\\1c&HF2F2F2&\\3c&H7A7A7A&\\bord4\\shad6"
                      f"\\fscx60\\fscy60\\t(0,140,\\fscx100\\fscy100)}}{num}")
    Path(ruta).write_text(head + "\n".join(ev) + "\n")


def fusionar(rs):
    out = []
    for a, b in sorted(tuple(x) for x in rs):
        if out and a <= out[-1][1] + 0.05:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def lanzar_matte(p, vsegs):
    """Máscara de la persona (Apple Vision) solo para los tramos del crudo que usa el reel; queda en caché."""
    prof = EST.get("profundidad", {})
    binario = MOTOR / "bin" / "matte"
    if not prof.get("activo") or not binario.exists():
        return None
    matte, meta = pesado(p, "matte.mp4"), pesado(p, "matte.json")
    nec = fusionar([(max(0.0, v["s0"] - 0.3), v["s1"] + 0.4) for v in vsegs])
    if matte.exists():
        cub = json.loads(meta.read_text())["rangos"] if meta.exists() else [[0, 1e9]]
        if all(any(c0 <= a and b <= c1 for c0, c1 in cub) for a, b in nec):
            return None
        nec = fusionar(nec + [tuple(x) for x in cub if x[1] < 1e8])
    tmp = pesado(p, "matte.tmp.mp4")
    cmd = [str(binario), str(p / "fuente.mp4"), str(tmp), "--rangos", ",".join(f"{a:.2f}-{b:.2f}" for a, b in nec)]
    if prof.get("objetos"):
        cmd.append("--objetos")
    pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    pr.meta = (tmp, matte, meta, nec)
    return pr


def esperar_matte(pr):
    if pr is None:
        return
    out, err = pr.communicate()
    tmp, matte, meta, nec = pr.meta
    if pr.returncode:
        print(f"  (máscara falló, sigo sin profundidad: {err[-300:]})"); return
    tmp.replace(matte)
    meta.write_text(json.dumps({"rangos": nec}))
    if os.environ.get("REEL_DEBUG"): print("  " + out.strip())


def cobertura_matte(p, ts, caja):
    """Fracción de la caja (x0,y0,x1,y1 en 1080x1920) que tapa la silueta de la persona en el segundo ts del crudo."""
    m = pesado(p, "matte.mp4")
    if not m.exists():
        return None
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ts:.3f}", "-i", str(m), "-frames:v", "1",
                          "-vf", "scale=108:192,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    if len(raw) < 108 * 192:
        return None
    x0, y0, x1, y1 = (int(v / 10) for v in caja)
    vals = [raw[y * 108 + x] for y in range(max(0, y0), min(192, y1)) for x in range(max(0, x0), min(108, x1))]
    return sum(v > 127 for v in vals) / max(1, len(vals))


def eventos_sonido(graf, graf_sfx, brolls, vsegs, golpes_t=()):
    """Diseño sonoro: cada elemento visual dispara su efecto (sonido.json); se respetan separación y prioridad."""
    mapa_f = SFX / "sonido.json"
    if not mapa_f.exists():
        return []
    mapa = json.loads(mapa_f.read_text())
    evs, sep = mapa["eventos"], mapa.get("separacion_min", 0.35)
    por_comp = {"Titulo": "titulo", "Firma": "firma", "Tarjeta": "tarjeta", "Cierre": "cierre", "Heroe": "heroe"}
    crudos = []
    for g in graf:
        e = por_comp.get(g["comp"])
        if g["comp"] == "Pop":
            e = "emoji" if g["props"].get("tipo") == "emoji" else "logo"
        elif g["comp"] in ("Escena", "Frase"):
            e = "broll"
        if e:
            crudos.append((g["t0"], e))
    crudos += [(g["t0"], "logo") for g in graf_sfx]
    crudos += [(b["t0"], "broll") for b in brolls]
    for a_g in golpes_t:
        crudos.append((a_g, "golpe"))
    elegidos = []
    for t, e in sorted(crudos):
        if e not in evs or not (SFX / evs[e]["archivo"]).exists():
            continue
        pr = evs[e].get("prioridad", 0)
        if elegidos and t - elegidos[-1][0] < sep:
            if pr > evs[elegidos[-1][1]].get("prioridad", 0):
                elegidos[-1] = (t, e)
            continue
        elegidos.append((t, e))
    return [(t, evs[e]) for t, e in elegidos]


def entregar(p, ed, final):
    """Entregados/<fecha>_<tema>/ sin pisar otro proyecto; la versión previa del mismo proyecto va a anteriores/."""
    c = ed.get("copy", {})
    tema = slugify(ed.get("slug") or c.get("titulo") or p.name.split("_", 1)[-1])
    base = ENTREGADOS / f"{p.name.split('_')[0]}_{tema}"
    dest, k = base, 2
    while dest.exists() and not ((dest / ".proyecto").exists() and (dest / ".proyecto").read_text().strip() == p.name):
        dest = base.with_name(f"{base.name}-{k}"); k += 1
    dest.mkdir(parents=True, exist_ok=True)
    if (dest / "video.mp4").exists():
        viejo = dest / "anteriores" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        viejo.mkdir(parents=True)
        for f in ("video.mp4", "copy.md", "portada.jpg"):
            if (dest / f).exists():
                shutil.move(str(dest / f), viejo / f)
    for src, nombre in ((final, "video.mp4"), (EXPORTADOS / f"{p.name}_copy.md", "copy.md"),
                        (EXPORTADOS / f"{p.name}_portada.jpg", "portada.jpg")):
        shutil.copy(src, dest / f".{nombre}.tmp")
        (dest / f".{nombre}.tmp").replace(dest / nombre)
    (dest / ".proyecto").write_text(p.name)
    return dest


def beats_musica(pista, total):
    """Golpes de la música (onsets de percusión) en segundos, para cortar al ritmo."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(pista), "-t", f"{total + 1:.2f}", "-ac", "1", "-ar", "8000",
                          "-af", "highpass=f=40,lowpass=f=180", "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h", raw)
    hop = 80  # 10 ms
    e = [sum(x * x for x in a[i:i + hop]) / hop for i in range(0, len(a) - hop, hop)]
    flujo = [max(0.0, e[i] - e[i - 1]) for i in range(1, len(e))]
    if not flujo:
        return []
    umbral = sorted(flujo)[int(len(flujo) * 0.93)]
    beats, ult = [], -1.0
    for i in range(1, len(flujo) - 1):
        if flujo[i] >= umbral and flujo[i] >= flujo[i - 1] and flujo[i] >= flujo[i + 1] and (i + 1) / 100 - ult > 0.22:
            ult = (i + 1) / 100
            beats.append(round(ult, 2))
    return beats


def al_beat(t, beats, tol=0.15):
    if not beats:
        return t
    b = min(beats, key=lambda x: abs(x - t))
    return b if abs(b - t) <= tol else t


def huella_graficos():
    h = hashlib.sha1()
    for f in sorted(list((MOTOR / "src").rglob("*")) + [MOTOR / "graficos.mjs"] + sorted(FUENTES.glob("*"))):
        if f.is_file():
            h.update(f.name.encode()); h.update(f.read_bytes())
    return h.hexdigest()[:12]


class Caras:
    """Cara con Apple Vision (bin/caras): posición y tamaño cada 0.1 s; sirve en planos abiertos."""
    def __init__(self, p):
        f = p / "caras.json"
        if not f.exists() and (MOTOR / "bin" / "caras").exists():
            subprocess.run([str(MOTOR / "bin" / "caras"), str(p / "fuente.mp4"), str(f)], capture_output=True)
        self.c = [x for x in json.loads(f.read_text())["cuadros"] if x[1] is not None] if f.exists() else []

    def en(self, a, b):
        pts = [x for x in self.c if a - 0.05 <= x[0] <= b + 0.05] or self.c
        if not pts:
            return None
        med = lambda i: sorted(x[i] for x in pts)[len(pts) // 2]
        return med(1), med(2), med(4)

    def alto(self):
        return sorted(x[4] for x in self.c)[len(self.c) // 2] if self.c else None


def expr_k(vs):
    """Factor de zoom animado sobre el encuadre base (variable 'on' = cuadro de salida): empuje suave + punch-ins expo-out."""
    N = max(1, vs["nf"])
    e = f"(1+{vs['z1'] / vs['z0'] - 1:.4f}*(on/{N})*(on/{N})*(3-2*on/{N})"
    for pt, amt in vs.get("punch", []):
        f0 = round(pt * FPS)
        e += f"+{amt:.3f}*gte(on,{f0})*(1-pow(2,-10*(on-{f0})/6))"
    return e + ")"


def zoom_max(vs):
    """Zoom más cerrado que alcanza el segmento (empuje + punch-ins): para medir espacio de forma conservadora."""
    return vs["z1"] * (1 + sum(a for _, a in vs.get("punch", [])))


def encuadre(vs):
    """Rectángulo base (normalizado) para el zoom vs['z0']: la cara queda centrada y a ~36% de altura."""
    zb = vs["z0"]
    if zb <= 1.0005:
        return 0.0, 0.0
    w_, h_ = 1 / zb, 1 / zb
    if vs.get("reencuadre"):
        l0 = min(max(vs["cx"] - w_ / 2, 0), 1 - w_)
        t0 = min(max(vs["cy"] - EST.get("camara", {}).get("cara_altura", 0.41) * h_, 0), 1 - h_)
    else:  # zoom sobre la cara (como antes)
        l0, t0 = vs["cx"] * (1 - w_), vs["cy"] * (1 - h_)
    return l0, t0


def filtro_camara(vs, escala=""):
    if abs(vs["z0"] - 1) < 0.001 and abs(vs["z1"] - 1) < 0.001 and not vs.get("punch"):
        return escala
    K, zb = expr_k(vs), vs["z0"]
    l0, t0 = encuadre(vs)
    fx, fy = vs["cx"], vs["cy"]
    pre = ""
    if zb > 1.0005:
        # Recorta primero el encuadre base (estático): perspective trabaja con ~1/zb² de los píxeles y el
        # resultado es el mismo. Entrada: copia 4K (2W×2H) si hay escala, si no la fuente/máscara a W×H.
        iw, ih = (2 * W, 2 * H) if escala else (W, H)
        cw, ch = 2 * round(iw / zb / 2), 2 * round(ih / zb / 2)
        cx0, cy0 = min(max(round(l0 * iw), 0), iw - cw), min(max(round(t0 * ih), 0), ih - ch)
        pre = f",crop={cw}:{ch}:{cx0}:{cy0}"
        fx, fy = (fx * iw - cx0) / cw, (fy * ih - cy0) / ch
        l0 = t0 = 0.0; zb = 1.0
        escala = escala or f",scale={W}:{H}"
    # sub-rectángulo que se cierra sobre la cara dentro del encuadre base (unidades del input: W, H)
    L = f"({fx:.4f}*W-({fx:.4f}-{l0:.4f})*W/{K})"
    T = f"({fy:.4f}*H-({fy:.4f}-{t0:.4f})*H/{K})"
    ancho, alto = f"(W/({zb:.4f}*{K}))", f"(H/({zb:.4f}*{K}))"
    return (f"{pre},perspective=x0='{L}':y0='{T}':x1='{L}+{ancho}':y1='{T}':x2='{L}':y2='{T}+{alto}':"
            f"x3='{L}+{ancho}':y3='{T}+{alto}':interpolation=cubic:eval=frame{escala}")


def fuente_hd(p):
    """Copia 4K SDR del crudo para reencuadrar planos abiertos sin perder nitidez (se hace una vez)."""
    hd = pesado(p, "fuente_hd.mp4")
    if hd.exists():
        return hd
    origen = Path((p / "origen.txt").read_text().strip())
    if not origen.exists():
        return None
    i = info(origen)
    if min(i["w"], i["h"]) < 2000:
        return None
    vf = [f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase:flags=lanczos,crop={W * 2}:{H * 2}"]
    if i["hdr"]:
        vf.append(TONEMAP)
    vf.append("format=yuv420p")
    tmp = pesado(p, "fuente_hd.tmp.mp4")
    sh(["ffmpeg", "-y", "-hwaccel", "videotoolbox", "-i", str(origen), "-map", "0:v:0", "-an", "-vf", ",".join(vf),
        "-r", str(FPS), "-c:v", "h264_videotoolbox", "-b:v", "45M", "-g", "30", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-colorspace", "bt709", str(tmp)])
    tmp.replace(hd)
    return hd


def render(a):
    t_ini = time.time()
    p = Path(a.proyecto).expanduser().resolve()
    lineas = {l["id"]: l for l in json.loads((p / "lineas.json").read_text())}
    ed = json.loads((p / "edicion.json").read_text())
    dur_src = info(p / "fuente.mp4")["dur"]
    mir = Mirada(p)
    try:
        _m = json.loads((p / "mirada.json").read_text())
        _con = sum(1 for x in _m.get("cuadros", []) if x[2] is not None)
        if _m.get("cuadros") and _con < 0.1 * len(_m["cuadros"]):
            print("  (la mirada no detectó la cara en este plano: se ignora la lectura)")
            mir.regreso = lambda t, maximo=1.0: 0.0
            mir.cola = lambda t, maximo=0.6: 0.0
            mir.fuera = lambda a, b: []
    except Exception:
        pass
    en = Energia(p / "voz16k.wav") if (p / "voz16k.wav").exists() else None

    # 1) piezas de audio: líneas elegidas, partidas en sus silencios internos
    piezas = []
    for ref in ed["lineas"]:
        lid, sl = parse_ref(ref)
        if lid not in lineas:
            sys.exit(f"{lid} no existe")
        ws = [dict(w, lid=lid) for w in lineas[lid]["palabras"][sl]]
        for i_, w in enumerate(ws):
            if inflada(w, w is lineas[lid]["palabras"][0] or w["t0"] == lineas[lid]["palabras"][0]["t0"]):
                letras = len(re.sub(r"\W", "", w["w"]))
                ws[i_] = dict(w, t0=round(w["t1"] - (0.08 * letras + 0.22), 3), inflada=True)
        if not ws:
            continue
        idx_linea = len(piezas)
        run = [ws[0]]
        for w in ws[1:]:
            hueco = w["t0"] - run[-1]["t1"] > EST.get("gap_corte", GAP_CORTE)
            if hueco and en:  # Whisper a veces inventa pausas: solo se parte si de verdad hay silencio
                a_, b_ = run[-1]["t1"] - 0.05, w["t0"] + 0.05
                hueco = any(en.quieto(a_ + i * 0.01, a_ + i * 0.01 + 0.1) for i in range(max(0, int((b_ - a_ - 0.1) * 100)) + 1))
            if hueco:
                piezas.append({"palabras": run, "linea": lid}); run = []
            run.append(w)
        piezas.append({"palabras": run, "linea": lid, "recorte_fin": sl.stop is not None and sl.stop != 0})
        if sl.start:
            piezas[idx_linea]["recorte_ini"] = True
    todas = sorted(((w["t1"] - 0.6) if inflada(w, i == 0) else w["t0"], w["t1"])
                   for l in lineas.values() for i, w in enumerate(l["palabras"]))
    ini_s = [x[0] for x in todas]
    for k, pz in enumerate(piezas):
        w0, w1 = pz["palabras"][0], pz["palabras"][-1]
        pz["s0"] = max(0, w0["t0"] - EST.get("pre", PRE))
        pz["s1"] = min(dur_src, w1["t1"] + (0.5 if k == len(piezas) - 1 else EST.get("post", POST)))
        if en:
            # vecinos en el crudo: el corte no puede invadir la palabra anterior / siguiente
            i0 = bisect.bisect_left(ini_s, w0["t0"] - 0.005)
            prev_t1 = todas[i0 - 1][1] if i0 > 0 else 0.0
            i1 = bisect.bisect_right(ini_s, w1["t0"] + 0.005)
            next_t0 = todas[i1][0] if i1 < len(todas) else dur_src
            if w0.get("inflada"):
                # toma repetida escondida: la palabra real empieza en el silencio más profundo justo antes de su final
                cands = [round(w0["t1"] - 0.6 + i * 0.01, 2) for i in range(55)]
                a_ = min(cands, key=lambda t: (round(en.nivel(t)), -t)) + 0.05  # se compensa el margen de abajo: corta justo en el hueco
            else:
                a_ = en.inicio(w0["t0"], max(prev_t1 + 0.02, w0["t0"] - 0.35))
                real = en.arranque_real(w0["t0"], w0["t1"])
                if real:  # ruido antes de la palabra (silla, respiración): corta en el valle justo antes de la voz real
                    cands = [round(real - 0.3 + i * 0.01, 2) for i in range(29)]
                    a_ = min(cands, key=lambda t: (round(en.nivel(t)), -t)) + 0.05
            b_ = en.fin(w1["t1"], min(next_t0 - 0.02, w1["t1"] + 0.45))
            pz["s0"] = max(0, a_ - 0.05)
            pz["s1"] = min(dur_src, b_ + (0.5 if k == len(piezas) - 1 else 0.08))
            if os.environ.get("REEL_DEBUG"):
                print(f"  corte {pz['linea']}: entra {en.nivel(pz['s0']):.0f} dB (whisper {w0['t0']:.2f}→{pz['s0']:.2f}) · sale {en.nivel(pz['s1']):.0f} dB (whisper {w1['t1']:.2f}→{pz['s1']:.2f}) · umbral {en.umbral:.0f}")
    min_sil, pad = EST.get("silencio_min", 0), EST.get("silencio_pad", 0.04)
    if en and min_sil:
        nuevas = []
        for pz in piezas:
            a0, a1 = pz["s0"], pz["s1"]
            runs, ini, t = [], None, a0 + 0.06
            while t < a1 - 0.08:
                # un chasquido o respiro de ≤40 ms dentro de un silencio no lo parte en dos (la pausa sí se quita)
                blip = (ini is not None and en.nivel(t) < en.fuerte
                        and any(en.nivel(t + k * 0.01) < en.umbral for k in range(1, 5)))
                if en.nivel(t) < en.umbral or blip:
                    ini = t if ini is None else ini
                else:
                    if ini is not None and t - ini >= min_sil:
                        runs.append((ini, t))
                    ini = None
                t = round(t + 0.01, 2)
            bordes = [a0] + [x for r in runs for x in (r[0] + pad, r[1] - pad)] + [a1]
            segs = [(bordes[j], bordes[j + 1]) for j in range(0, len(bordes), 2)]
            asign = [[] for _ in segs]
            for w in pz["palabras"]:
                tras = [max(0.0, min(w["t1"], b1) - max(w["t0"], b0)) for b0, b1 in segs]
                mid = (w["t0"] + w["t1"]) / 2
                j_ = max(range(len(segs)), key=lambda j: (tras[j], -min(abs(mid - segs[j][0]), abs(mid - segs[j][1]))))
                asign[j_].append(w)
            vivos = [j for j, ws_ in enumerate(asign) if ws_]
            for j, ((b0, b1), ws_) in enumerate(zip(segs, asign)):
                if not ws_:
                    continue  # voz sin texto (toma repetida que Whisper omitió o muletilla)
                nuevas.append({"palabras": ws_, "linea": pz["linea"], "s0": b0, "s1": b1, "corto": j > 0,
                               "recorte_ini": pz.get("recorte_ini", False) and j == vivos[0],
                               "recorte_fin": pz.get("recorte_fin", False) and j == vivos[-1]})
        piezas = nuevas
    fus = []
    for pz in piezas:
        # se juntan tramos casi contiguos, salvo que entre la última palabra y la siguiente haya un silencio que
        # habría que quitar (el quitado de silencios ya corrió por pieza; juntarlas lo devolvería como pausa)
        hueco_voz = (pz["palabras"][0]["t0"] - fus[-1]["palabras"][-1]["t1"]) if fus and pz["palabras"] and fus[-1]["palabras"] else 0
        if (fus and pz["s0"] - fus[-1]["s1"] < 0.15 and pz["s0"] > fus[-1]["s0"]
                and not (EST.get("silencio_min") and hueco_voz >= 0.22)):
            fus[-1]["s1"] = pz["s1"]; fus[-1]["palabras"] += pz["palabras"]; fus[-1]["lineas"].add(pz["linea"])
            fus[-1]["recorte_fin"] = pz.get("recorte_fin", False)
        else:
            if fus and pz["s0"] < fus[-1]["s1"]:
                pz["s0"] = fus[-1]["s1"]
            pz["lineas"] = {pz["linea"]}
            fus.append(pz)
    piezas = fus

    # correcciones de texto (se definen en marca.json y en edicion.json)
    corr = [(c.split(), r) for c, r in ed.get("correcciones", {}).items()]
    for pz in piezas:
        ws = [dict(w) for w in pz["palabras"]]
        for frase, rep in corr:
            n_, k = len(frase), 0
            while k + n_ <= len(ws):
                if [norm(x["w"]) for x in ws[k:k + n_]] == [norm(x) for x in frase]:
                    punt = re.search(r"[.,?!:;…]*$", ws[k + n_ - 1]["w"])[0]
                    ws[k] = {"w": rep + punt, "t0": ws[k]["t0"], "t1": ws[k + n_ - 1]["t1"], "lid": ws[k].get("lid")}
                    del ws[k + 1:k + n_]
                k += 1
        pz["palabras"] = ws

    # 2) timeline de salida en tiempo final: cada pieza dura un número entero de cuadros ya acelerada
    vel = EST.get("velocidad", 1.0)
    t = 0.0
    for pz in piezas:
        pz["s0"] = round(pz["s0"], 4)  # el audio corta con precisión de milisegundo (no a la rejilla de cuadros)
        nf_ = max(1, round((pz["s1"] - pz["s0"]) / vel * FPS))
        pz["s1"] = round(pz["s0"] + nf_ / FPS * vel, 4)
        pz["o0"] = t
        t = round(t + nf_ / FPS, 4)
        pz["o1"] = t
    total = t
    # música (se elige antes para poder cortar al ritmo)
    m = ed.get("musica", "auto")
    pistas = sorted(x for x in MUSICA.rglob("*.*") if x.suffix.lower() in {".wav", ".mp3", ".m4a", ".aac"})
    pista = (MUSICA / m) if m not in ("auto", "none", None) else (pistas[sum(map(ord, p.name)) % len(pistas)] if pistas and m == "auto" else None)
    beats = beats_musica(pista, total) if pista and pista.exists() and EST.get("al_ritmo", True) else []

    # 3) J-cuts guiados por la mirada: la imagen cambia cuando ya mira a cámara
    cubrir = []      # tramos de salida que conviene tapar con broll
    d = [0.0] * (len(piezas) + 1)
    for k in range(1, len(piezas)):
        ret = q(mir.regreso(piezas[k]["s0"]))
        if ret <= 0.05:
            continue
        cola = q(mir.cola(piezas[k - 1]["s1"]))
        d[k] = min(ret, cola, q(piezas[k]["s1"] - piezas[k]["s0"] - 0.2))
        if ret - d[k] > 0.1:
            cubrir.append((piezas[k]["o0"] - 0.4, piezas[k]["o0"] + ret / vel + 0.6, piezas[k]["linea"]))
    for pz in piezas:
        for a0, a1 in mir.fuera(pz["s0"] + 0.3, pz["s1"]):
            cubrir.append((pz["o0"] + (a0 - pz["s0"]) / vel - 0.3, pz["o0"] + (a1 - pz["s0"]) / vel + 0.4, pz["linea"]))
    caras = Caras(p)
    lf = p / "lineas_fijas.json"
    if not lf.exists() and VENV_PY.exists() and EST.get("lineas_guia"):
        subprocess.run([str(VENV_PY), str(MOTOR / "lineas_fijas.py"), str(p / "fuente.mp4"), str(lf),
                        ",".join(str(x) for x in EST["lineas_guia"])], capture_output=True)
    filas_guia = json.loads(lf.read_text())["filas"] if lf.exists() else []
    alto_cara = caras.alto()
    cam_cfg = EST.get("camara", {})
    reenc = 1.0
    if alto_cara and alto_cara < cam_cfg.get("plano_abierto", 0.085):
        reenc = min(cam_cfg.get("reencuadre_max", 1.8), cam_cfg.get("cara_objetivo", 0.115) / alto_cara)
        print(f"  plano abierto (cara {alto_cara:.1%} del alto): reencuadre a {reenc:.2f}x")
    vsegs = []
    golpes = {parse_ref(x if isinstance(x, str) else x["linea"])[0] for x in ed.get("golpes", []) if isinstance(x, str) or x.get("linea")}
    frase_max = EST.get("frase_max", 0)
    for k, pz in enumerate(piezas):
        vs0, vs1 = pz["s0"] + d[k], min(dur_src, pz["s1"] + d[k + 1])
        # estilo editor: un encuadre distinto en cada frase (corta en la puntuación o cada ~frase_max s)
        cortes, ult = [vs0], vs0
        ws_ = pz["palabras"]
        for i, w in enumerate(ws_[:-1]):
            t = (w["t1"] + ws_[i + 1]["t0"]) / 2
            if frase_max and (re.search(r"[.,?!:;…]$", w["w"]) or t - ult >= frase_max) and t - ult >= 1.2 and vs1 - t >= 1.0:
                cortes.append(t); ult = t
        cortes.append(vs1)
        for j in range(len(cortes) - 1):
            a0, a1 = cortes[j], cortes[j + 1]
            lid_v = next((w.get("lid") for w in ws_ if w["t0"] >= a0 - 0.05), pz["linea"])
            cv = caras.en(a0, a1)
            cx, cy = (cv[0], cv[1]) if cv else mir.cara(a0, a1)
            corto_v = (a1 - a0) / vel < 0.45
            if (j == 0 and k > 0 and pz.get("corto") and pz["linea"] == piezas[k - 1]["linea"] and pz["s0"] - piezas[k - 1]["s1"] < 0.25) or (corto_v and vsegs):
                z = vsegs[-1]["z"] if not vsegs[-1].get("bn") else EST["zoom"][0]
            else:
                z = EST["zoom"][sum(1 for v in vsegs if v.get("nuevo")) % len(EST["zoom"])]
            bn = False  # el golpe B/N ahora es una ventana de tiempo (ver ventanas_golpe)
            nuevo = not ((j == 0 and k > 0 and pz.get("corto") and pz["linea"] == piezas[k - 1]["linea"] and pz["s0"] - piezas[k - 1]["s1"] < 0.25) or (corto_v and vsegs))
            zz = (EST.get("zoom_golpe", 1.3) if bn else z) * reenc
            empuje = cam_cfg.get("empuje", 0.0)
            if ed.get("cta") and pz["linea"] == parse_ref(ed["cta"]["linea"])[0]:
                zz, empuje = reenc, 0.0   # cierre estable: el CTA cabe arriba de la cabeza
            vsegs.append({"s0": round(a0, 4), "s1": round(a1, 4), "z": zz, "z0": zz, "z1": zz * (1 + empuje),
                          "cx": cx, "cy": cy, "bn": bn, "nuevo": nuevo, "reencuadre": reenc > 1.0})

    def mapear(ts, pz):
        return round(pz["o0"] + (min(max(ts, pz["s0"]), pz["s1"]) - pz["s0"]) / vel, 3)

    # cuadros y tiempo final de cada segmento de video
    nfs = [max(1, round((vs["s1"] - vs["s0"]) / vel * FPS)) for vs in vsegs]
    acum = [0]
    for x in nfs:
        acum.append(acum[-1] + x)
    if acum[-1] != round(total * FPS):  # el video manda: ajusta el último segmento al total del audio
        nfs[-1] += round(total * FPS) - acum[-1]
        acum[-1] = round(total * FPS)
    for k, vs in enumerate(vsegs):
        vs["o0"], vs["nf"] = acum[k] / FPS, nfs[k]
    esperar_precalentar(p)
    pr_matte = lanzar_matte(p, vsegs)

    def a_fuente(t_out):
        v = next((v for v in vsegs if v["o0"] <= t_out < v["o0"] + v["nf"] / FPS), vsegs[-1])
        return v["s0"] + (t_out - v["o0"]) * vel

    enf = {norm(x) for x in ed.get("enfasis", [])}
    palabras, linea_t = [], {}
    for pi, pz in enumerate(piezas):
        for w in pz["palabras"]:
            palabras.append({"texto": w["w"], "t0": mapear(w["t0"], pz), "t1": mapear(w["t1"], pz),
                             "enfasis": norm(w["w"]) in enf or bool(re.fullmatch(r"\d+[\d.,%]*[.,?!:;…]*", w["w"])),
                             "pieza": pi, "lid": w.get("lid") or pz["linea"]})
            # tiempos por línea desde sus palabras (piezas fusionadas pueden contener varias líneas)
            lid = w.get("lid") or pz["linea"]
            r = linea_t.setdefault(lid, [palabras[-1]["t0"], palabras[-1]["t1"]])
            r[0], r[1] = min(r[0], palabras[-1]["t0"]), max(r[1], palabras[-1]["t1"])

    # golpes B/N: ventanas cortas sobre la frase dura (dict con "palabra" o línea entera → arranque de la línea)
    ventanas_golpe = []
    for gp in ed.get("golpes", []):
        gd = gp if isinstance(gp, dict) else {"linea": gp}
        lid_g = parse_ref(gd["linea"])[0] if gd.get("linea") else None
        r_g = buscar_palabra(palabras, gd["palabra"], lid_g) if gd.get("palabra") else None
        t_g = r_g[0] if r_g else (linea_t[lid_g][0] if lid_g in linea_t else None)
        if t_g is not None:
            ventanas_golpe.append((round(t_g - 0.05, 3), round(t_g - 0.05 + gd.get("dur", 1.3), 3)))
    for a_g, _ in ventanas_golpe:  # entra con un punch fuerte
        v = next((v for v in vsegs if v["o0"] <= a_g < v["o0"] + v["nf"] / FPS), None)
        if v:
            amt = min(0.14, reenc * cam_cfg.get("zoom_total_max", 1.32) / zoom_max(v) - 1)
            if amt >= 0.03:
                v.setdefault("punch", []).append((round(max(0.0, a_g - v["o0"]), 3), round(amt, 3)))

    # punch-ins de cámara: en las palabras de énfasis (o las de "punch"), espaciados y fuera del título
    cam = EST.get("camara", {})
    if cam.get("punch_max", 0):
        objetivo = {norm(x) for x in (ed.get("punch") or [])}
        cands = [w for w in palabras if (norm(w["texto"]) in objetivo if objetivo else w["enfasis"])]
        ult = -9.0
        for w in cands:
            if sum(len(v.get("punch", [])) for v in vsegs) >= cam["punch_max"]:
                break
            if w["t0"] < 3.8 or w["t0"] - ult < cam.get("punch_sep", 2.5):
                continue
            if ed.get("cta") and parse_ref(ed["cta"]["linea"])[0] in linea_t and w["t0"] > linea_t[parse_ref(ed["cta"]["linea"])[0]][0] - 0.3:
                continue  # el cierre va estable para que el CTA no choque con la cabeza
            if any(a_g - 0.3 <= w["t0"] <= b_g for a_g, b_g in ventanas_golpe):
                continue
            v = next((v for v in vsegs if v["o0"] <= w["t0"] < v["o0"] + v["nf"] / FPS), None)
            if not v or v["bn"] or w["t0"] - v["o0"] < 0.25:
                continue
            tp = al_beat(w["t0"] - 0.04, beats, 0.12)
            if not (v["o0"] + 0.2 <= tp < v["o0"] + v["nf"] / FPS - 0.2):
                tp = w["t0"] - 0.04
            amt = min(cam.get("punch", 0.07), reenc * cam.get("zoom_total_max", 1.32) / zoom_max(v) - 1)
            if amt < 0.03:
                continue
            v.setdefault("punch", []).append((round(tp - v["o0"], 3), round(amt, 3)))
            ult = w["t0"]

    # 4) páginas de subtítulos (frases cortas)
    st = EST["subtitulos"]
    paginas, cur = [], []
    for k, w in enumerate(palabras):
        cur.append(k)
        txt = " ".join(palabras[j]["texto"] for j in cur)
        nxt = palabras[k + 1] if k + 1 < len(palabras) else None
        if (len(cur) >= st["max_palabras"] or len(txt) >= st["max_chars"] or re.search(r"[.,?!:;…]$", w["texto"])
                or nxt is None or nxt["pieza"] != w["pieza"] or nxt["t0"] - w["t1"] > 0.25):
            paginas.append(cur); cur = []
    pags = []
    for k, idx in enumerate(paginas):
        fin = palabras[idx[-1]]["t1"] + 0.3
        if k + 1 < len(paginas):
            fin = min(fin, palabras[paginas[k + 1][0]]["t0"])
        pags.append({"t0": palabras[idx[0]]["t0"], "t1": min(fin, total), "palabras": idx})
    editor = EST.get("modo") == "editor"          # B-roll de Pexels, pops/emojis, golpes, barra
    look_editor = EST.get("look") == "editor"     # subtítulos 1–3 palabras + título fijo (si no: look premium de la marca)
    extra_subs = {"total": total, "cta": (ed.get("cta") or {}).get("palabra"),
                  "cta_lid": parse_ref(ed["cta"]["linea"])[0] if ed.get("cta") else None}
    if look_editor:
        pags = paginas_editor(palabras, total)
        lista = ed.get("lista")
        if not lista and any(tj.get("num") is not None for tj in ed.get("tarjetas", [])):
            lista = {"titulo": ed.get("gancho", ""), "items": [{"linea": tj["linea"], "num": tj["num"]} for tj in ed["tarjetas"]]}
        if lista:
            marcas = sorted((linea_t[parse_ref(it["linea"])[0]][0], it["num"]) for it in lista["items"] if parse_ref(it["linea"])[0] in linea_t)
            extra_subs["lista"] = {"titulo": lista["titulo"], "marcas": marcas}
        elif ed.get("gancho") and ed.get("titulo_fijo", True):
            extra_subs["titulo"] = ed.get("titulo") or ed["gancho"]

    def escribir_subs(pg_):
        if look_editor:
            escribir_ass_editor(palabras, pg_, p / "subtitulos.ass", extra_subs)
        else:
            escribir_ass(palabras, pg_, p / "subtitulos.ass")
    escribir_subs(pags)

    # 5) gráficos (Remotion con alfa, caché por contenido)
    graf = []  # {comp, props, t0, dur, sfx}
    tarjetas = []
    for tj in ed.get("tarjetas", []):
        lid = parse_ref(tj["linea"])[0]
        if lid in linea_t:
            r = linea_t[lid]
            tarjetas.append((r[0], r[1] + 0.35, tj))
    for i in range(len(tarjetas) - 1):
        a0, a1, tj = tarjetas[i]
        tarjetas[i] = (a0, min(a1, tarjetas[i + 1][0] - 0.05), tj)
    def y_sobre_cara(t_out, dur, alto_bloque, y_def):
        """Posición de un bloque de texto superior que no toque la cara (incluido el pelo); si no cabe arriba, va abajo."""
        en_v = [v for v in vsegs if v["o0"] < t_out + dur and v["o0"] + v["nf"] / FPS > t_out] or [vsegs[0]]
        v = max(en_v, key=zoom_max)      # el momento más cerrado de la ventana
        z = zoom_max(v)
        l0, t0_ = encuadre(dict(v, z0=z))
        src0 = v["s0"]
        cv = caras.en(src0, v["s1"])
        if not cv:
            return y_def, False
        fy_out, fh_out = (cv[1] - t0_) * z * H, cv[2] * z * H
        arriba = fy_out - fh_out * 1.05 - 70   # pelo rizado + aire
        if y_def + alto_bloque <= arriba:
            return y_def, False
        if arriba - alto_bloque >= 110:
            return int(arriba - alto_bloque), False
        return int(min(1180, fy_out + fh_out * 0.9 + 40)), True

    cta_t0 = None
    if ed.get("cta") and parse_ref(ed["cta"]["linea"])[0] in linea_t:
        cta_t0 = linea_t[parse_ref(ed["cta"]["linea"])[0]][0]
    if look_editor:
        tarjetas, cta_t0 = [], None
    if ed.get("gancho") and not look_editor:
        fin = min(3.6, tarjetas[0][0] if tarjetas else 3.6)
        y_t, abajo = y_sobre_cara(0.0, fin, 330, 200)
        graf.append({"comp": "Titulo", "props": {"eyebrow": ed.get("eyebrow") or MARCA["eyebrow"], "texto": ed["gancho"],
                                                 "y": y_t, "abajo": abajo},
                     "t0": 0.0, "dur": fin, "sfx": "brillo"})
    firma = {"nombre": MARCA["nombre"], "rol": MARCA["rol"], "mostrar": MARCA.get("mostrar_firma", True)}
    if firma.get("mostrar") and firma["nombre"] and not look_editor:
        f0 = (graf[0]["dur"] + 0.6) if graf else 1.0
        if not any(t0 < f0 + 3.2 and t1 > f0 for t0, t1, _ in tarjetas):
            graf.append({"comp": "Firma", "props": {"nombre": firma["nombre"], "rol": firma["rol"]},
                         "t0": f0, "dur": 3.2, "sfx": None})
    for t0, t1, tj in tarjetas:
        props = {"texto": tj["texto"]}
        if tj.get("num") is not None:
            props["num"] = tj["num"]
        graf.append({"comp": "Tarjeta", "props": props, "t0": t0, "dur": t1 - t0, "sfx": "whoosh"})
    if EST.get("destellos", True) and not look_editor:
        tit = next((g for g in graf if g["comp"] == "Titulo"), None)
        if tit:
            graf.append({"comp": "Destello", "props": {"lado": "izq"}, "t0": max(0, tit["t0"] + tit["dur"] - 0.35), "dur": 0.9, "sfx": None})
        if cta_t0 is not None and cta_t0 > 6:
            graf.append({"comp": "Destello", "props": {"lado": "der"}, "t0": cta_t0 - 0.45, "dur": 0.9, "sfx": None})
    if cta_t0 is not None:
        y_c, abajo_c = y_sobre_cara(cta_t0, min(3.0, total - cta_t0), 330, 230)
        compacto = False
        if abajo_c:  # no cabe el bloque normal arriba de la cabeza: versión compacta pegada arriba
            y_c2, abajo_c2 = y_sobre_cara(cta_t0, min(3.0, total - cta_t0), 235, 70)
            if not abajo_c2:
                y_c, compacto = y_c2, True
        graf.append({"comp": "Cierre", "props": {"texto": ed["cta"].get("texto", MARCA["cta_texto"]),
                                                  "palabra": ed["cta"]["palabra"], "y": y_c, "compacto": compacto},
                     "t0": cta_t0, "dur": total - cta_t0, "sfx": "hit"})
    if editor:
        def t_de(x):
            r_ = buscar_palabra(palabras, x["palabra"], parse_ref(x["linea"])[0] if x.get("linea") else None) if x.get("palabra") else None
            if r_:
                return r_[0]
            lid_ = parse_ref(x["linea"])[0] if x.get("linea") else None
            return linea_t[lid_][0] + 0.15 if lid_ in linea_t else None
        for pp in ed.get("pops", []):
            t0 = t_de(pp)
            if t0 is None or (cta_t0 is not None and t0 > cta_t0 - 0.3):
                continue  # el CTA va limpio
            props = {"tipo": pp.get("tipo", "logo"), "iconos": pp.get("iconos", []), "texto": pp.get("texto", ""), "lado": pp.get("lado", "izq")}
            graf.append({"comp": "Pop", "props": props, "t0": max(0, al_beat(t0 - 0.1, beats, 0.12)), "dur": pp.get("dur", {"usa": 2.4, "emoji": 1.1}.get(props["tipo"], 1.6)), "sfx": "brillo"})
        bar = ed.get("barra")
        if bar:
            ts = [(t_de(it), it["icono"]) for it in bar["items"]]
            ts = sorted(x for x in ts if x[0] is not None)
            if ts:
                b0 = max(0, ts[0][0] - 0.1)
                hasta = t_de({"linea": bar["hasta"]}) if bar.get("hasta") else None
                b1 = min(total, hasta or ts[-1][0] + 3.0)
                graf.append({"comp": "Barra", "props": {"items": [{"icono": ic, "at": round(t - 0.1 - b0, 3)} for t, ic in ts]},
                             "t0": b0, "dur": b1 - b0, "sfx": None})
                for t, _ in ts:
                    graf.append({"comp": None, "t0": t - 0.1, "dur": 0, "sfx": "brillo"})
    CACHE.mkdir(parents=True, exist_ok=True)
    graf_sfx = [g for g in graf if g["comp"] is None]
    graf = [g for g in graf if g["comp"]]
    t_g = time.time()

    # 6) broll: pedidos explícitos + tapar uniones con lectura visible
    catalogo = json.loads((BROLL / "catalogo.json").read_text()) if (BROLL / "catalogo.json").exists() else []
    brolls = []
    if catalogo and not editor:
        usados = set()

        def elegir(tema):
            ops = [c for c in catalogo if (not tema or c["tema"] == tema) and c["id"] not in usados] or \
                  [c for c in catalogo if c["id"] not in usados] or catalogo
            c = ops[sum(map(ord, p.name + str(len(usados)))) % len(ops)]
            usados.add(c["id"]); return c
        for b in ed.get("broll", []):
            lid = parse_ref(b["linea"])[0]
            if lid in linea_t:
                r = linea_t[lid]
                brolls.append({"t0": r[0] + 0.2, "dur": min(b.get("dur", 2.8), r[1] - r[0]), "clip": elegir(b.get("tema"))})
        con_visual = {parse_ref(v["linea"])[0] for v in ed.get("visuales", [])}
        for c0, c1, lid_c in sorted(cubrir):
            if lid_c in con_visual:
                continue  # esa unión la tapa su escena de motion graphics
            if len(brolls) >= EST["broll_por_video"] + len(ed.get("broll", [])):
                break
            c0 = max(c0, 0.5)
            if c1 - c0 < 0.4 or any(c0 < b["t0"] + b["dur"] and c1 > b["t0"] for b in brolls):
                continue
            brolls.append({"t0": c0, "dur": max(1.6, c1 - c0), "clip": elegir(None)})
    if editor:
        usados_px = set()
        for b in ed.get("broll", []):
            if not b.get("buscar"):
                continue
            r_ = buscar_palabra(palabras, b["palabra"], parse_ref(b["linea"])[0] if b.get("linea") else None) if b.get("palabra") else None
            if not r_ and b.get("linea") and parse_ref(b["linea"])[0] in linea_t:
                r_ = (linea_t[parse_ref(b["linea"])[0]][0] + 0.2, None)
            if not r_:
                print(f"  B-roll sin ubicar: {b}"); continue
            dur_b = b.get("dur", 2.0)
            t0 = max(0.3, al_beat(r_[0] - 0.12, beats))
            corte_prev = [v["o0"] for v in vsegs if t0 - 0.55 <= v["o0"] < t0]
            if corte_prev:
                dur_b += t0 - corte_prev[-1]; t0 = corte_prev[-1]
            if t0 + dur_b > total - 0.3 or any(t0 < x["t0"] + x["dur"] + 0.2 and t0 + dur_b > x["t0"] - 0.2 for x in brolls):
                continue
            clip = pexels_clip(b["buscar"], dur_b, usados_px)
            if clip:
                brolls.append({"t0": t0, "dur": dur_b, "clip": clip})
    # palabras héroe DETRÁS de la persona (máscara): nunca en el título, B-roll, firma ni CTA
    heroes_cfg = EST.get("heroe", {})
    if ed.get("heroes") and EST.get("profundidad", {}).get("activo"):
        esperar_matte(pr_matte); pr_matte = None
        prohib = [(x["t0"], x["t0"] + x["dur"]) for x in brolls] + \
                 [(g["t0"], g["t0"] + g["dur"]) for g in graf if g["comp"] in ("Titulo", "Cierre")]
        for hz in ed["heroes"][:heroes_cfg.get("max", 2)]:
            r_ = buscar_palabra(palabras, hz["palabra"], parse_ref(hz["linea"])[0] if hz.get("linea") else None)
            if not r_:
                print(f"  héroe sin ubicar: {hz['palabra']}"); continue
            t0, dur_h = max(0.0, r_[0] - 0.08), hz.get("dur", heroes_cfg.get("dur", 1.7))
            # termina con su frase (no invade la siguiente)
            w_h = next((w for w in palabras if w["t0"] >= r_[0] - 0.01), None)
            if w_h:
                fin_frase = max(x["t1"] for x in palabras if x["pieza"] == w_h["pieza"])
                dur_h = max(heroes_cfg.get("dur_min", 1.5), min(dur_h, fin_frase + 0.6 - t0))
                sig = [b["t0"] for b in brolls if b["t0"] > t0 + 0.3]   # puede cruzar al golpe B/N (dorado sobre gris queda bien)
                if sig:
                    dur_h = min(dur_h, min(sig) - t0 - 0.05)
            if any(t0 < b and t0 + dur_h > a for a, b in prohib) or t0 + dur_h > total - 0.2:
                print(f"  héroe «{hz['palabra']}» choca con título/B-roll/firma/CTA: se omite"); continue
            texto = hz.get("texto") or re.sub(r"[.,?!:;…]+$", "", hz["palabra"])
            tam = min(270, round(1000 / (len(texto) * 0.78 + 0.3)))
            muestras = [t0 + 0.15, t0 + dur_h * 0.5, t0 + dur_h - 0.15]
            mejor = None
            for y in heroes_cfg.get("ys", [380, 520, 660, 800]):
                ancho = min(1040, len(texto) * tam * 0.78)
                cobs = []
                for tm in muestras:
                    v = next((v for v in vsegs if v["o0"] <= tm < v["o0"] + v["nf"] / FPS), vsegs[-1])
                    z = zoom_max(v)
                    l0, t0_ = encuadre(dict(v, z0=z))
                    # la caja en pantalla vista en el crudo (deshace el encuadre de ese segmento)
                    caja = ((l0 + (W - ancho) / 2 / W / z) * W, (t0_ + y / H / z) * H,
                            (l0 + (W + ancho) / 2 / W / z) * W, (t0_ + (y + tam) / H / z) * H)
                    c_ = cobertura_matte(p, v["s0"] + (tm - v["o0"]) * vel, caja)
                    if c_ is not None:
                        cobs.append(c_)
                if not cobs:
                    break
                cob = max(cobs)
                puntaje = abs(cob - heroes_cfg.get("tapado", 0.25)) + (2 if cob > 0.18 else 0)
                if mejor is None or puntaje < mejor[0]:
                    mejor = (puntaje, y, cob)
            if mejor and mejor[2] > heroes_cfg.get("tapado_max", 0.3):
                print(f"  héroe «{hz['palabra']}» quedaría {mejor[2]:.0%} tapado: se omite (elige otra palabra)"); continue
            y_h = mejor[1] if mejor else 520
            if os.environ.get("REEL_DEBUG") and mejor:
                print(f"  héroe «{texto}» en {t0:.1f}s · y={y_h} · tapado {mejor[2]:.0%}")
            graf.append({"comp": "Heroe", "props": {"texto": texto, "y": y_h, "tam": tam}, "t0": t0, "dur": dur_h,
                         "sfx": "heroe", "detras": True})
            prohib.append((t0, t0 + dur_h))
    # la firma nunca va sobre B-roll ni sobre una palabra héroe: se mueve al primer hueco libre
    ocupado = [(x["t0"], x["t0"] + x["dur"]) for x in brolls] + \
              [(g["t0"], g["t0"] + g["dur"]) for g in graf if g["comp"] in ("Heroe", "Pop")] + \
              list(ventanas_golpe)
    for g in graf:
        if g["comp"] == "Firma":
            t_ = g["t0"]
            while t_ + g["dur"] < total - 0.5 and any(t_ < b_ + 0.2 and t_ + g["dur"] > a_ - 0.2 for a_, b_ in ocupado):
                t_ = round(t_ + 0.1, 2)
            g["t0"] = t_
    no_cubiertos = [c for c in cubrir if not any(c[0] < b["t0"] + b["dur"] and c[1] > b["t0"] for b in brolls)]
    if editor and ed.get("broll_relleno"):
        qs = ed["broll_relleno"]
        for i, (c0, c1, lid_c) in enumerate(sorted(no_cubiertos)):
            c0 = max(c0, 0.4)
            dur_b = min(max(1.4, c1 - c0), 2.4)
            fin_ok = (cta_t0 - 0.2) if cta_t0 is not None else total - 0.3
            firma_v = [(g["t0"], g["t0"] + g["dur"]) for g in graf if g["comp"] in ("Firma", "Heroe")]
            if c0 + dur_b > fin_ok or any(c0 < x["t0"] + x["dur"] + 0.3 and c0 + dur_b > x["t0"] - 0.3 for x in brolls) \
                    or any(c0 < f1 and c0 + dur_b > f0 for f0, f1 in firma_v):
                continue
            clip = pexels_clip(qs[i % len(qs)], dur_b, usados_px)
            if clip:
                brolls.append({"t0": c0, "dur": dur_b, "clip": clip})
        no_cubiertos = [c for c in cubrir if not any(c[0] < b["t0"] + b["dur"] and c[1] > b["t0"] for b in brolls)]
    # sin "parpadeos": si entre dos B-roll queda menos de 0.6 s de la persona, el primero se alarga hasta el segundo
    brolls.sort(key=lambda x: x["t0"])
    for i_ in range(len(brolls) - 1):
        hueco = brolls[i_ + 1]["t0"] - (brolls[i_]["t0"] + brolls[i_]["dur"])
        if 0 < hueco < 0.6:
            brolls[i_]["dur"] += hueco
    huella = huella_graficos()
    # tapar cortes con motion graphics (Remotion, gratis): escena del 'visual' de esa línea o, si no hay, la frase
    visuales = {parse_ref(v["linea"])[0]: v for v in ed.get("visuales", [])}
    insertos, ocultar_subs = [], []
    fijos = [(g["t0"], g["t0"] + g["dur"]) for g in graf if g["comp"] in ("Titulo",)]

    def libre(c0, c1):
        return c1 <= total - 0.3 and not any(c0 < b + 0.15 and c1 > a - 0.15 for a, b in fijos + insertos)

    usados_v = set()

    def poner(c0, c1, lid):
        v = visuales.get(lid) if lid not in usados_v else None
        if v:
            usados_v.add(lid)
            props = {"tipo": v.get("tipo", "icono"), "texto": v.get("texto", ""), "iconos": v.get("iconos", [])}
            if v.get("valor"):
                props["valor"] = str(v["valor"])
            graf.append({"comp": "Escena", "props": props, "t0": c0, "dur": c1 - c0, "sfx": "whoosh"})
        else:
            sig = [w for w in palabras if w["t0"] >= c0 - 0.05][:7]
            corte = next((i + 1 for i, w in enumerate(sig) if re.search(r"[.,?!:;…]$", w["texto"]) and i >= 2), len(sig))
            texto = " ".join(w["texto"] for w in sig[:corte]).rstrip(",;:")
            if not texto:
                return
            graf.append({"comp": "Frase", "props": {"texto": texto}, "t0": c0, "dur": c1 - c0, "sfx": "whoosh"})
            ocultar_subs.append((c0, c1))
        insertos.append((c0, c1))

    # 1) cortes con lectura visible (ventanas cercanas se fusionan)
    ventanas = []
    for c0, c1, lid in sorted(no_cubiertos):
        c0, c1 = max(c0, 0.3), max(c1, c0 + EST.get("inserto_min", 1.5))
        c1 = min(c1, c0 + EST.get("inserto_max_dur", 2.8))
        if ventanas and c0 < ventanas[-1][1] + 0.6 and max(c1, ventanas[-1][1]) - ventanas[-1][0] <= EST.get("inserto_max_dur", 2.8):
            ventanas[-1][1] = max(ventanas[-1][1], c1)
        else:
            ventanas.append([c0, c1, lid])
    if not EST.get("tapar_con_escenas", True):
        ventanas, visuales = [], {}
    for c0, c1, lid in ventanas:
        if len(insertos) >= EST.get("insertos_max", 12):
            break
        for a_, b_ in fijos:  # justo después del título: empezar al terminar
            if a_ <= c0 < b_ + 0.15:
                c0 = b_ + 0.15; c1 = max(c1, c0 + 1.2)
        # si lee casi todo el video la ventana es enorme: tapar solo el arranque del corte
        c1 = min(c1, c0 + EST.get("inserto_max_dur", 2.8), total - 0.35)
        if os.environ.get("REEL_DEBUG"):
            print(f"  ventana {c0:.1f}-{c1:.1f} {lid} libre={libre(c0, c1)}")
        if libre(c0, c1):
            poner(c0, c1, lid)
    # 2) visuales pedidos en líneas que no necesitaban tapar
    for lid, v in visuales.items():
        if lid in linea_t and lid not in usados_v and not any(a <= linea_t[lid][0] + 0.3 < b for a, b in insertos):
            c0 = linea_t[lid][0] + 0.2
            c1 = min(linea_t[lid][1], c0 + v.get("dur", 1.8))
            if c1 - c0 >= 1.0 and libre(c0, c1):
                poner(c0, c1, lid)
    no_cubiertos = [c for c in no_cubiertos if not any(c[0] < b and c[1] > a for a, b in insertos)]
    if ocultar_subs:
        pags = [pg for pg in pags if not any(pg["t0"] < b and pg["t1"] > a for a, b in ocultar_subs)]
        escribir_subs(pags)
    logo_uri = None
    for g in graf:
        g["props"]["duracion"] = round(g["dur"], 3)
        g["props"]["marca"] = marca_props()
        if g["comp"] in ("Cierre", "Escena", "Explicador"):   # los que dibujan el logo
            logo_uri = logo_uri if logo_uri is not None else logo_data_uri()
            g["props"]["marca"]["logo"] = logo_uri
        h = hashlib.sha1(json.dumps([g["comp"], g["props"], huella], sort_keys=True).encode()).hexdigest()[:16]
        g["out"] = str(CACHE / f"{g['comp']}-{h}.mov")
    (p / "graficos.json").write_text(json.dumps(graf, ensure_ascii=False))
    sh(["node", "graficos.mjs", str(p / "graficos.json")], cwd=MOTOR)
    esperar_matte(pr_matte); pr_matte = None
    t_g = time.time() - t_g

    # 7) video en bloques paralelos (uno por núcleo) + una pasada de audio; se unen sin recomprimir
    t_f = time.time()
    fuente = str(p / "fuente.mp4")
    ass = str(p / "subtitulos.ass").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    fd = str(FUENTES).replace(":", "\\:").replace("'", "\\'")
    n, nv = len(piezas), len(vsegs)
    total_f = acum[-1]
    prof = EST.get("profundidad", {})
    matte = pesado(p, "matte.mp4")
    usar_matte = bool(prof.get("activo")) and matte.exists()
    lut = REC / "lut" / EST.get("lut", "")
    if EST.get("lut") and not lut.exists() and (MOTOR / "hacer_lut.py").exists():
        lut.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(MOTOR / "hacer_lut.py"), str(lut)], capture_output=True)
    grade = f"lut3d=file='{lut}':interp=tetrahedral" if EST.get("lut") and lut.exists() else EST["color"]
    hd = fuente_hd(p) if max(v["z1"] for v in vsegs) * (1 + cam_cfg.get("punch", 0)) > 1.3 else None
    fuente_v = str(hd) if hd else fuente
    escala_v = f",scale={W}:{H}:flags=lanczos" if hd else ""
    nb = max(1, min(EST.get("bloques", 6), nv))
    bloques, ini = [], 0
    for k in range(nv):
        if acum[k + 1] - acum[ini] >= total_f / nb or k == nv - 1:
            bloques.append((ini, k + 1)); ini = k + 1
    tmp = pesado(p, "bloques")
    shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir()

    def cmd_bloque(bi, a_, b_):
        T0, T1 = acum[a_] / FPS, acum[b_] / FPS
        ins, fc = [], []
        m_ = b_ - a_
        for j, k in enumerate(range(a_, b_)):
            vs = vsegs[k]
            ins += ["-hwaccel", "videotoolbox", "-ss", f"{vs['s0']:.4f}", "-t", f"{vs['s1'] - vs['s0'] + 0.2:.4f}", "-i", fuente_v]
            cam_f = filtro_camara(vs, escala_v)
            bn = ",hue=s=0,eq=contrast=1.12" if vs.get("bn") else ""
            base = f"setpts=(PTS-STARTPTS)/{vel},fps={FPS},trim=end_frame={nfs[k]},setpts=PTS-STARTPTS"
            ent = f"[{j}:v]{base}"
            if filas_guia:
                h_in = H * 2 if hd else H
                g = 3 if hd else 2
                ultimo = None
                for i_r, yn in enumerate(filas_guia):
                    y_ = round(yn * h_in)
                    src_ = ultimo or ent
                    fc.append(f"{src_},split=3[ra{j}_{i_r}][ru{j}_{i_r}][rd{j}_{i_r}]" if ultimo is None else
                              f"[{ultimo}]split=3[ra{j}_{i_r}][ru{j}_{i_r}][rd{j}_{i_r}]")
                    fc.append(f"[ru{j}_{i_r}]crop=iw:{2 * g + 1}:0:{y_ - 3 * g - 1}[uu{j}_{i_r}]")
                    fc.append(f"[rd{j}_{i_r}]crop=iw:{2 * g + 1}:0:{y_ + g + 1}[dd{j}_{i_r}]")
                    fc.append(f"[uu{j}_{i_r}][dd{j}_{i_r}]blend=all_mode=average[bb{j}_{i_r}]")
                    fc.append(f"[ra{j}_{i_r}][bb{j}_{i_r}]overlay=0:{y_ - g}[rf{j}_{i_r}]")
                    ultimo = f"rf{j}_{i_r}"
                ent = f"[{ultimo}]null"
            fc.append(f"{ent}{cam_f}{bn},format=yuv420p,setsar=1[v{j}]")
        if usar_matte:
            for j, k in enumerate(range(a_, b_)):
                vs = vsegs[k]
                ins += ["-ss", f"{vs['s0']:.4f}", "-t", f"{vs['s1'] - vs['s0'] + 0.2:.4f}", "-i", str(matte)]
                base = f"setpts=(PTS-STARTPTS)/{vel},fps={FPS},trim=end_frame={nfs[k]},setpts=PTS-STARTPTS"
                fc.append(f"[{m_ + j}:v]{base}{filtro_camara(vs)},format=gray,setsar=1[m{j}]")
        vg = [(max(a_g, T0) - T0, min(b_g, T1) - T0) for a_g, b_g in ventanas_golpe if a_g < T1 and b_g > T0]
        bn_f = "".join(f",hue=s=0:enable='between(t,{a:.3f},{b:.3f})',eq=contrast=1.12:enable='between(t,{a:.3f},{b:.3f})'" for a, b in vg)
        fc.append("".join(f"[v{j}]" for j in range(m_)) + f"concat=n={m_}:v=1:a=0{bn_f}[vc]")
        idx = m_ * (2 if usar_matte else 1)
        heroes_b = [g for g in graf if g.get("detras") and g["t0"] < T1 and g["t0"] + g["dur"] > T0]
        if usar_matte:
            fc.append("".join(f"[m{j}]" for j in range(m_)) + f"concat=n={m_}:v=1:a=0,gblur=sigma={prof.get('pluma', 2)}[mc]")
            ns = 2 if heroes_b else 1
            fc.append(f"[vc]{grade},{EST.get('ajuste_piel', 'null')},format=yuv420p,split={ns + 1}[g0]" + "".join(f"[g{i + 1}]" for i in range(ns)))
            fc.append(f"[mc]split={ns}" + "".join(f"[mm{i}]" for i in range(ns)))
            osc, des, sat = prof.get("oscurecer", 0.08), prof.get("desenfoque", 3), 1 - prof.get("desat", 0.1)
            fc.append(f"[g0]scale={W // 2}:{H // 2},gblur=sigma={des / 2:.2f},scale={W}:{H},"
                      f"eq=brightness={-osc:.3f}:saturation={sat:.3f},format=yuva420p[bg]")
            fc.append("[g1][mm0]alphamerge[fg0]")
            fc.append("[bg][fg0]overlay=format=auto,format=yuv420p[dep]")
            cur = "dep"
            if heroes_b:
                fc.append("[g2][mm1]alphamerge[fgh]")
                fc.append("[fgh]split=" + str(len(heroes_b)) + "".join(f"[fgh{i}]" for i in range(len(heroes_b))))
                for i, g in enumerate(heroes_b):
                    c0, c1 = g["t0"], g["t0"] + g["dur"]
                    off, r0 = max(0.0, T0 - c0), max(c0, T0) - T0
                    ins += ["-ss", f"{off:.4f}", "-i", g["out"]]
                    fc.append(f"[{idx}:v]setpts=PTS-STARTPTS+{r0:.4f}/TB[h{i}]")
                    en_ = f"enable='between(t,{r0:.4f},{c1 - T0:.4f})'"
                    fc.append(f"[{cur}][h{i}]overlay=eof_action=pass:{en_}[hh{i}]")
                    fc.append(f"[hh{i}][fgh{i}]overlay={en_}[hf{i}]")
                    cur, idx = f"hf{i}", idx + 1
        else:
            fc.append(f"[vc]{grade},{EST.get('ajuste_piel', 'null')},format=yuv420p[dep]")
            cur = "dep"
        acab = []
        if EST.get("vineta"):
            acab.append(f"vignette=angle={EST['vineta']}")
        if EST.get("grano"):
            acab.append(f"noise=c0s={EST['grano']}:c0f=t")
        fc.append(f"[{cur}]" + (",".join(acab) + "," if acab else "") + "format=yuv420p[x0]")
        cur = "x0"
        capas = [("b", b) for b in brolls] + [("g", g) for g in graf if not g.get("detras")]
        for j, (tipo, c) in enumerate(capas):
            c0, c1 = c["t0"], c["t0"] + c["dur"]
            if c1 <= T0 or c0 >= T1:
                continue
            off = max(0.0, T0 - c0)
            r0 = max(c0, T0) - T0
            if tipo == "g":
                ins += ["-ss", f"{off:.4f}", "-i", c["out"]]
                fc.append(f"[{idx}:v]setpts=PTS-STARTPTS+{r0:.4f}/TB[c{j}]")
            else:
                ins += ["-i", str(BROLL / c["clip"]["archivo"])]
                d_ = c["dur"]
                fb = EST.get("broll_fundido", 0.25)
                zb = "(1+0.12*pow(max(0,1-on/6),2))"   # entrada con zoom rápido 1.12 → 1.0
                ent = (f"perspective=x0='540*(1-1/{zb})':y0='960*(1-1/{zb})':x1='540*(1-1/{zb})+W/{zb}':y1='960*(1-1/{zb})':"
                       f"x2='540*(1-1/{zb})':y2='960*(1-1/{zb})+H/{zb}':x3='540*(1-1/{zb})+W/{zb}':y3='960*(1-1/{zb})+H/{zb}':"
                       f"interpolation=cubic:eval=frame,") if off < 0.01 else ""
                fc.append(f"[{idx}:v]trim=duration={d_:.3f},setpts=PTS-STARTPTS,scale={W}:{H}:force_original_aspect_ratio=increase,"
                          f"crop={W}:{H},{ent}{grade},format=yuva420p,fade=t=in:d={fb:.3f}:alpha=1,"
                          f"fade=t=out:st={d_ - fb:.3f}:d={fb:.3f}:alpha=1,trim=start={off:.4f},setpts=PTS-STARTPTS+{r0:.4f}/TB[c{j}]")
            fc.append(f"[{cur}][c{j}]overlay=eof_action=pass:enable='between(t,{r0:.4f},{c1 - T0:.4f})'[x{j + 1}]")
            cur, idx = f"x{j + 1}", idx + 1
        fc.append(f"[{cur}]setpts=PTS+{T0:.4f}/TB,subtitles=filename='{ass}':fontsdir='{fd}',setpts=PTS-STARTPTS,format=yuv420p[vout]")
        (tmp / f"f{bi}.txt").write_text(";\n".join(fc))
        hilos = str(max(2, (os.cpu_count() or 8) // nb))
        cmd = ["ffmpeg", "-y", "-v", "error", "-filter_threads", hilos, "-threads", hilos, *ins, "-/filter_complex", str(tmp / f"f{bi}.txt"), "-map", "[vout]",
                "-an", "-frames:v", str(acum[b_] - acum[a_]), "-r", str(FPS), "-c:v", "h264_videotoolbox", "-b:v", "18M",
                "-profile:v", "high", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
                str(tmp / f"b{bi:02d}.mp4")]
        (tmp / f"c{bi}.json").write_text(json.dumps(cmd))
        return cmd

    # audio: voz pulida + música con ducking + sfx (pasada propia, rápida)
    ains, afc = [], []
    for k, pz in enumerate(piezas):
        dd = pz["s1"] - pz["s0"]
        ains += ["-ss", f"{pz['s0']:.4f}", "-t", f"{dd + 0.05:.4f}", "-i", fuente]
        afc.append(f"[{k}:a]asetpts=PTS-STARTPTS,atrim=duration={dd:.4f},"
                   f"afade=t=in:d=0.03,afade=t=out:st={max(0, dd - 0.03):.4f}:d=0.03[a{k}]")
    afc.append("".join(f"[a{k}]" for k in range(n)) + f"concat=n={n}:v=0:a=1[ac]")
    afc.append(f"[ac]atempo={vel},highpass=f=80,afftdn=nf=-28,acompressor=threshold=-20dB:ratio=3:attack=5:release=90:makeup=2,"
               "aresample=48000,asplit=2[voz][vkey]")
    idx, mezcla = n, ["[voz]"]
    if pista and pista.exists():
        ains += ["-stream_loop", "-1", "-i", str(pista)]
        fin_voz = palabras[-1]["t1"] if palabras else total
        afc.append(f"[{idx}:a]atrim=duration={total:.3f},aresample=48000,aformat=channel_layouts=stereo,"
                   f"equalizer=f=2500:t=o:w=1.3:g=-4,"          # le deja espacio a la voz (medios)
                   f"volume='{EST['musica_volumen']}*if(gt(t,{fin_voz:.2f}),1.7,1)':eval=frame,"  # sube al terminar de hablar
                   f"afade=t=in:d=0.8,afade=t=out:st={max(0, total - 1.2):.3f}:d=1.2[mus]")
        afc.append("[mus][vkey]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=250[mduck]")
        mezcla.append("[mduck]"); idx += 1
    else:
        afc.append("[vkey]anullsink")
    for j, (t0, ev) in enumerate(eventos_sonido(graf, graf_sfx, brolls, vsegs, [a for a, _ in ventanas_golpe])):
        ains += ["-i", str(SFX / ev["archivo"])]
        afc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={ev['db']}dB,"
                   f"adelay={int(max(0, t0 - ev.get('antes', 0)) * 1000)}:all=1[s{j}]")
        mezcla.append(f"[s{j}]"); idx += 1
    afc.append("".join(mezcla) + f"amix=inputs={len(mezcla)}:normalize=0:duration=first,"
               "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,aformat=channel_layouts=stereo[aout]")
    (tmp / "audio.txt").write_text(";\n".join(afc))
    trabajos = [subprocess.Popen(cmd_bloque(bi, a_, b_), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                for bi, (a_, b_) in enumerate(bloques)]
    trabajos.append(subprocess.Popen(["ffmpeg", "-y", "-v", "error", *ains, "-/filter_complex", str(tmp / "audio.txt"),
                                      "-map", "[aout]", "-t", f"{total:.3f}", "-c:a", "aac", "-b:a", "192k",
                                      str(tmp / "audio.m4a")], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True))
    t_tr = time.time()
    for tr in trabajos:
        _, err = tr.communicate()
        if os.environ.get("REEL_DEBUG"): print(f"  trabajo listo a los {time.time() - t_tr:.0f}s")
        if tr.returncode:
            sys.exit(f"ERROR en ffmpeg (bloque):\n{err[-3000:]}")
    (tmp / "lista.txt").write_text("".join(f"file 'b{bi:02d}.mp4'\n" for bi in range(len(bloques))))
    EXPORTADOS.mkdir(exist_ok=True)
    final = EXPORTADOS / f"{p.name}.mp4"
    sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "lista.txt"), "-i", str(tmp / "audio.m4a"),
        "-map", "0:v", "-map", "1:a", "-c", "copy", "-movflags", "+faststart", str(final)])
    if not os.environ.get("REEL_DEBUG"): shutil.rmtree(tmp, ignore_errors=True)
    t_f = time.time() - t_f

    # 8) entregables + QA de uniones (una sola imagen, solo si hace falta revisarla)
    sh(["ffmpeg", "-y", "-ss", "1.4", "-i", str(final), "-frames:v", "1", "-q:v", "3",
        str(EXPORTADOS / f"{p.name}_portada.jpg")])
    uniones = [pz["o0"] + d[k] / vel + 0.07 for k, pz in enumerate(piezas) if k][:12]
    if uniones:
        sel = "+".join(f"eq(n\\,{int(u * FPS)})" for u in uniones)
        sh(["ffmpeg", "-y", "-i", str(final), "-vf", f"select='{sel}',scale=180:-1,tile={min(6, len(uniones))}x{(len(uniones) + 5) // 6}",
            "-frames:v", "1", "-q:v", "4", str(p / "qa_uniones.jpg")])
    c = ed.get("copy", {})
    (EXPORTADOS / f"{p.name}_copy.md").write_text(
        f"# {c.get('titulo','')}\n\n{c.get('caption','')}\n\n{' '.join(c.get('hashtags', []))}\n")
    # timeline para la revisión de calidad (todo en tiempo final)
    cortes_qa, pausas_qa = [], []
    if en:
        for k, pz in enumerate(piezas):
            if k:
                cortes_qa.append({"t": pz["o0"], "lado": "entra", "nivel": en.nivel(pz["s0"]), "deliberado": bool(pz.get("recorte_ini"))})
            if k < len(piezas) - 1:
                cortes_qa.append({"t": pz["o1"], "lado": "sale", "nivel": max(en.nivel(pz["s1"] - x * 0.01) for x in range(3)),
                                  "deliberado": bool(pz.get("recorte_fin"))})
            ini, t_ = None, pz["s0"] + 0.05
            fin_p = pz["s1"] - (0.5 if k == len(piezas) - 1 else 0.05)
            while t_ < fin_p:
                if en.nivel(t_) < en.umbral:
                    ini = t_ if ini is None else ini
                elif ini is not None:
                    if t_ - ini >= 0.2:
                        pausas_qa.append({"t": round(pz["o0"] + (ini - pz["s0"]) / vel, 2), "dur": round((t_ - ini) / vel, 3)})
                    ini = None
                t_ = round(t_ + 0.01, 2)
    tl = {"total": total, "vel": vel, "umbral": en.umbral if en else -40, "cortes": cortes_qa, "pausas": pausas_qa,
          "palabras": [{"texto": w["texto"], "t0": w["t0"], "t1": w["t1"]} for w in palabras],
          "graficos": [{"comp": g["comp"], "t0": round(g["t0"], 2), "dur": round(g["dur"], 2)} for g in graf],
          "brolls": [{"t0": round(b["t0"], 2), "dur": round(b["dur"], 2), "clip": b["clip"]["archivo"]} for b in brolls],
          "sfx": [round(t, 2) for t, _ in eventos_sonido(graf, graf_sfx, brolls, vsegs, [a for a, _ in ventanas_golpe])]}
    (p / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))
    sys.path.insert(0, str(MOTOR))
    import qa as qa_mod
    res_qa = qa_mod.revisar(p, final)
    dest = None
    if res_qa["estado"] == "ok" or os.environ.get("REEL_FORZAR"):
        dest = entregar(p, ed, final)
        # el crudo pasa a 01-crudos/_procesados solo cuando la revisión pasa
        origen = Path((p / "origen.txt").read_text().strip())
        if origen.parent == RAIZ / "01-crudos" and origen.exists():
            (origen.parent / "_procesados").mkdir(exist_ok=True)
            nuevo = origen.parent / "_procesados" / origen.name
            shutil.move(str(origen), nuevo)
            (p / "origen.txt").write_text(str(nuevo))
    jc = sum(1 for x in d if x > 0)
    reps = repeticiones(palabras)
    infladas = sum(1 for pz in piezas for w in pz["palabras"] if w.get("inflada"))
    print(f"LISTO {total:.1f}s → {final}\n"
          f"piezas {len(piezas)} · J-cuts {jc} · broll {len(brolls)} · insertos {len(insertos)} · uniones con lectura sin tapar {len(no_cubiertos)}"
          f"{' en ' + ', '.join(f'{c[0]:.1f}s({c[2]})' for c in no_cubiertos) if no_cubiertos else ''}\n"
          f"tomas escondidas recortadas {infladas} · repeticiones en el reel {len(reps)}"
          f"{' → ' + '; '.join(f'{t:.1f}s «{x}»' for t, x in reps) if reps else ''}\n"
          f"QA {res_qa['estado'].upper()} · LUFS {res_qa['datos'].get('lufs')} · audio=guion {res_qa['datos'].get('similitud_audio_guion')}"
          f"{' · DUROS: ' + ' | '.join(res_qa['duros']) if res_qa['duros'] else ''}"
          f"{' · avisos: ' + ' | '.join(res_qa['avisos']) if res_qa['avisos'] else ''}\n"
          f"entregado: {dest or 'NO (la revisión falló; REEL_FORZAR=1 para entregar igual)'}\n"
          f"tiempo: gráficos {t_g:.0f}s · ffmpeg {t_f:.0f}s · total {time.time() - t_ini:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("preparar"); s.add_argument("video"); s.add_argument("--slug")
    s = sub.add_parser("render"); s.add_argument("proyecto")
    sub.add_parser("lote")
    s = sub.add_parser("txt"); s.add_argument("proyecto")
    s = sub.add_parser("precalentar"); s.add_argument("proyecto")
    a = ap.parse_args()
    if a.cmd == "precalentar":
        precalentar(a); sys.exit()
    if a.cmd == "txt":
        pp = Path(a.proyecto).expanduser().resolve()
        ls_ = json.loads((pp / "lineas.json").read_text())
        escribir_txt(pp, ls_, info(pp / "fuente.mp4")["dur"]); print((pp / "transcripcion.txt").read_text()); sys.exit()
    {"preparar": preparar, "render": render, "lote": lote}[a.cmd](a)
