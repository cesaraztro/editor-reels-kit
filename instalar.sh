#!/usr/bin/env bash
# Instalador del Editor de Reels (macOS).
#   ./instalar.sh               instala todo y copia la skill a ~/.claude/skills/editor-reels/
#   ./instalar.sh --sin-skill   instala todo menos la skill de Claude Code
#   ./instalar.sh --si          responde "sí" a las preguntas (por ejemplo, sobrescribir la skill)
#   ./instalar.sh --ayuda
# Es seguro correrlo varias veces: solo hace lo que falta.
set -u

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOTOR="$KIT/_motor"
SIN_SKILL=0
TODO_SI=0
for a in "$@"; do
  case "$a" in
    --sin-skill) SIN_SKILL=1 ;;
    --si) TODO_SI=1 ;;
    -h|--ayuda|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opción desconocida: $a (usa --ayuda)"; exit 2 ;;
  esac
done

if [ -t 1 ]; then V=$'\033[32m'; A=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'; B=$'\033[1m'; else V=""; A=""; R=""; N=""; B=""; fi
ok()    { echo "${V}  ✓${N} $*"; }
aviso() { echo "${A}  !${N} $*"; }
falla() { echo "${R}  ✗ $*${N}"; }
paso()  { echo; echo "${B}$*${N}"; }
PENDIENTES=()
faltante() { PENDIENTES+=("$1"); falla "$2"; }

echo "${B}Editor de Reels · instalación${N}"
echo "Carpeta del kit: $KIT"

# ---------------------------------------------------------------- 1. requisitos
paso "1/6 Revisando requisitos"
if [ "$(uname -s)" != "Darwin" ]; then
  falla "Este kit necesita macOS (usa Apple Vision para la silueta y la cara, y VideoToolbox para codificar)."
  exit 1
fi
ok "macOS $(sw_vers -productVersion 2>/dev/null)"
if [ "$(uname -m)" != "arm64" ]; then
  aviso "Tu Mac no es Apple Silicon (M1 o más nuevo): Whisper (mlx) no funcionará y el render será lento."
fi

if command -v ffmpeg >/dev/null 2>&1; then
  ok "ffmpeg: $(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f1-3)"
  ENC="$(ffmpeg -hide_banner -encoders 2>/dev/null)"; FIL="$(ffmpeg -hide_banner -filters 2>/dev/null)"
  echo "$ENC" | grep -q h264_videotoolbox || faltante "ffmpeg" "Tu ffmpeg no trae h264_videotoolbox. Instala la versión de Homebrew: brew install ffmpeg"
  echo "$FIL" | grep -qE ' subtitles ' || faltante "ffmpeg con libass" "Tu ffmpeg no trae el filtro 'subtitles' (libass). Instala la versión de Homebrew: brew install ffmpeg"
  echo "$FIL" | grep -qE ' lut3d ' || aviso "Tu ffmpeg no trae lut3d; el color se verá más plano."
else
  faltante "ffmpeg" "Falta ffmpeg. Instálalo con: brew install ffmpeg"
fi

if command -v node >/dev/null 2>&1; then
  NV="$(node -v | sed 's/^v//' | cut -d. -f1)"
  if [ "${NV:-0}" -ge 18 ]; then ok "node $(node -v)"; else faltante "node 18+" "Node $(node -v) es muy viejo; necesitas 18 o más (brew install node)."; fi
else
  faltante "node 18+" "Falta Node.js. Instálalo con: brew install node"
fi
command -v npm >/dev/null 2>&1 || faltante "npm" "Falta npm (viene con Node.js)."

if command -v python3 >/dev/null 2>&1; then ok "python3 $(python3 -V 2>&1 | cut -d' ' -f2)"; else faltante "python3" "Falta python3 (brew install python)."; fi

if command -v uv >/dev/null 2>&1 && command -v uvx >/dev/null 2>&1; then
  ok "uv $(uv --version 2>/dev/null | cut -d' ' -f2)"
else
  faltante "uv" "Falta uv (se usa para Whisper y el entorno de Python). Instálalo con: brew install uv"
fi

if command -v swiftc >/dev/null 2>&1 && xcode-select -p >/dev/null 2>&1; then
  ok "swiftc (Xcode Command Line Tools)"
else
  faltante "Xcode Command Line Tools" "Faltan las herramientas de Xcode (swiftc). Instálalas con: xcode-select --install"
fi

if [ "${#PENDIENTES[@]}" -gt 0 ]; then
  echo
  falla "Faltan requisitos: ${PENDIENTES[*]}. Instálalos y vuelve a correr ./instalar.sh"
  exit 1
fi

# ---------------------------------------------------------------- 2. dependencias de Remotion
paso "2/6 Instalando los gráficos (Remotion)"
cd "$MOTOR" || exit 1
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund >/tmp/editor-reels-npm.log 2>&1 || npm install --no-audit --no-fund >/tmp/editor-reels-npm.log 2>&1
else
  npm install --no-audit --no-fund >/tmp/editor-reels-npm.log 2>&1
fi
if [ $? -eq 0 ] && [ -d node_modules/remotion ]; then ok "paquetes de npm instalados"; else falla "npm falló. Mira /tmp/editor-reels-npm.log"; exit 1; fi
if npx --no-install remotion browser ensure >/tmp/editor-reels-chrome.log 2>&1; then ok "navegador de Remotion listo"; else aviso "No se pudo preparar el navegador de Remotion ahora; se descargará solo en el primer render (necesita internet)."; fi

# ---------------------------------------------------------------- 3. binarios de Apple Vision
paso "3/6 Compilando los programas de Apple Vision (silueta y cara)"
mkdir -p "$MOTOR/bin"
if swiftc -O -Ounchecked matte/matte.swift -o bin/matte >/tmp/editor-reels-swift.log 2>&1; then ok "bin/matte (silueta)"; else falla "No compiló matte.swift. Mira /tmp/editor-reels-swift.log"; exit 1; fi
if swiftc -O matte/caras.swift -o bin/caras >>/tmp/editor-reels-swift.log 2>&1; then ok "bin/caras (cara)"; else falla "No compiló caras.swift. Mira /tmp/editor-reels-swift.log"; exit 1; fi

# ---------------------------------------------------------------- 4. entorno de Python
paso "4/6 Preparando Python (detección de mirada y guías fijas)"
if [ ! -x "$MOTOR/.venv/bin/python" ]; then
  uv venv --python 3.12 "$MOTOR/.venv" >/tmp/editor-reels-venv.log 2>&1 || uv venv "$MOTOR/.venv" >>/tmp/editor-reels-venv.log 2>&1
fi
if uv pip install --python "$MOTOR/.venv/bin/python" -r "$MOTOR/requirements.txt" >>/tmp/editor-reels-venv.log 2>&1; then
  ok "entorno _motor/.venv listo (mediapipe + numpy)"
else
  falla "No se pudo instalar mediapipe. Mira /tmp/editor-reels-venv.log"; exit 1
fi

# ---------------------------------------------------------------- 5. recursos
paso "5/6 Generando recursos"
mkdir -p "$KIT/04-recursos/lut"
if [ ! -f "$KIT/04-recursos/lut/premium.cube" ]; then
  python3 "$MOTOR/hacer_lut.py" "$KIT/04-recursos/lut/premium.cube" >/dev/null && ok "LUT de color premium.cube"
else
  ok "LUT de color ya existe"
fi
if [ ! -f "$KIT/.env" ]; then
  cp "$KIT/.env.example" "$KIT/.env" && ok "creé .env (pega ahí tu PEXELS_API_KEY si quieres B-roll automático)"
fi
if [ ! -f "$KIT/marca.json" ]; then aviso "No hay marca.json: copia uno de ejemplos/ y edítalo."; else ok "marca.json encontrado (edítalo con tu marca)"; fi
if ls "$KIT"/04-recursos/sfx/pixabay/*.mp3 >/dev/null 2>&1; then ok "efectos de sonido encontrados"; else aviso "Sin efectos de sonido (opcional). Lee 04-recursos/sfx/README.md para descargarlos gratis."; fi
if ls "$KIT"/04-recursos/musica/*.mp3 "$KIT"/04-recursos/musica/*.wav "$KIT"/04-recursos/musica/*/* >/dev/null 2>&1; then ok "música encontrada"; else aviso "Sin música (opcional). Lee 04-recursos/musica/README.md."; fi

# ---------------------------------------------------------------- 6. skill de Claude Code
paso "6/6 Skill de Claude Code"
DEST="$HOME/.claude/skills/editor-reels"
if [ "$SIN_SKILL" -eq 1 ]; then
  aviso "Omitida por --sin-skill. Para instalarla después: ./instalar.sh"
else
  INSTALAR=1
  if [ -e "$DEST/SKILL.md" ]; then
    if [ "$TODO_SI" -eq 1 ]; then
      RESP="s"
    elif [ -t 0 ]; then
      read -r -p "  Ya existe $DEST/SKILL.md. ¿Sobrescribirla? (se guarda una copia .bak) [s/N] " RESP
    else
      RESP="n"
    fi
    case "$RESP" in
      s|S|si|sí|SI|Si|y|Y) cp "$DEST/SKILL.md" "$DEST/SKILL.md.bak-$(date +%Y%m%d-%H%M%S)" ;;
      *) INSTALAR=0; aviso "No se tocó tu skill existente." ;;
    esac
  fi
  if [ "$INSTALAR" -eq 1 ]; then
    mkdir -p "$DEST"
    sed "s#__RUTA_KIT__#$KIT#g" "$KIT/skill/editor-reels/SKILL.md" > "$DEST/SKILL.md"
    ok "skill instalada en $DEST (apunta a $KIT)"
  fi
fi

echo
echo "${V}${B}Listo.${N} Siguientes pasos:"
echo "  1. Edita ${B}marca.json${N} con tu nombre, colores y logo (cámbialo en logo/)."
echo "  2. Pon tus videos en ${B}01-crudos/${N}."
echo "  3. En Claude Code, dentro de esta carpeta, escribe: ${B}edita este video${N}."
echo "  (La primera vez Whisper descarga su modelo, ~1.6 GB.)"
