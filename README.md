# Editor de Reels

Convierte un video tuyo hablando a cámara en un reel vertical (1080×1920) con acabado de editor profesional, **todo en tu Mac y sin pagar suscripciones**. Lo manejas desde Claude Code: le dices "edita este video" y él elige las tomas, escribe la edición y entrega el reel ya revisado.

> Kit privado para miembros de la comunidad de Skool de César Holguín. Lee la [LICENSE](LICENSE) antes de usarlo.

## Qué hace

**Corte y ritmo**
- Corta en el silencio real de tu voz (nunca a media palabra), quita pausas y muletillas de arranque y acelera a 1.12× sin que se note.
- Descarta tomas repetidas: tú grabas varias veces la misma frase y se queda la mejor.
- Cambia el encuadre en cada corte (1.0× / 1.18×), con empuje suave y *punch-ins* en las palabras clave, alineados al ritmo de la música.
- Si grabaste en plano abierto, reencuadra solo a plano medio recortando desde una copia 4K.

**Imagen**
- Profundidad con tu silueta (Apple Vision): fondo ligeramente más oscuro y suave.
- Palabra héroe gigante **detrás de ti**, golpe en blanco y negro en la frase más dura, color de cine (LUT), viñeta y grano.
- Detecta cuándo lees fuera de cámara y lo tapa con B-roll o gráficos.

**Gráficos con tu marca** (colores, tipografías y logo salen de `marca.json`)
- Título animado, firma con tu nombre y rol, cierre con llamada a la acción y logo, destellos de luz.
- Subtítulos en caja de tu color, con las palabras clave resaltadas.
- Emojis, logos de herramientas reales (Simple Icons) y B-roll vertical de Pexels por palabra clave.
- Título y CTA **nunca tapan tu cara**: el motor mide dónde está y se acomoda arriba o abajo.

**Sonido y calidad**
- Música de fondo que se agacha bajo tu voz y sube al terminar; diseño sonoro (whooshes, pops, impactos); volumen final −14 LUFS.
- **Revisión de calidad automática**: cortes a media palabra, pausas, repeticiones, volumen y que el video final diga lo mismo que el guion. Si algo falla, no entrega.
- Un revisor independiente (un segundo agente de Claude) mira el resultado con una lista premium antes de que lo veas.

## Requisitos

- **Mac con Apple Silicon (M1 o más nuevo)** recomendado. La silueta y la cara usan Apple Vision, y la transcripción usa MLX: solo funcionan en Mac. En Intel el render es muy lento y no hay transcripción local.
- macOS reciente con las **herramientas de Xcode** (`xcode-select --install`).
- [Homebrew](https://brew.sh) y, con él: `brew install ffmpeg node uv` (ffmpeg completo: con VideoToolbox y libass; la versión de Homebrew los trae).
- Python 3 (el de macOS sirve) y [Claude Code](https://claude.com/claude-code).
- ~5 GB libres para dependencias y modelo de Whisper, más espacio para tus videos (cada reel genera cientos de MB temporales en `~/Movies/editor-reels-cache`, que puedes vaciar).

## Instalación

```bash
git clone <la dirección del repositorio privado> editor-reels-kit   # o descomprime el zip
cd editor-reels-kit
./instalar.sh
```

El script revisa lo que falta (y te dice cómo instalarlo), instala los paquetes de Remotion, compila los programas de Apple Vision, prepara el entorno de Python y copia la skill a `~/.claude/skills/editor-reels/` (si ya tenías una, te pregunta antes de sobrescribirla). Es seguro correrlo varias veces. Opciones: `--sin-skill` (no toca Claude Code) y `--si` (responde sí a todo).

La primera vez que edites, Whisper descarga su modelo (~1.6 GB) y Remotion su navegador interno.

**Mueve el kit de lugar con cuidado:** la skill apunta a la carpeta donde corriste `./instalar.sh`. Si la mueves, vuelve a correrlo. Mejor mantenlo fuera de carpetas sincronizadas (iCloud, Dropbox), por ejemplo en `~/Code/`.

## Configura tu marca

Edita **`marca.json`** (en la raíz). Todo lo visual sale de ahí:

| Campo | Qué es |
|---|---|
| `nombre`, `rol` | La firma que aparece una vez en el reel ("Tu Nombre · Fundador · TuMarca"). `mostrar_firma: false` la oculta. |
| `empresa`, `vocabulario`, `correcciones` | Ayudan a Whisper con nombres propios y corrigen cómo se escriben en los subtítulos. |
| `eyebrow` | La etiqueta pequeña sobre el título. |
| `cta_texto` | Texto por defecto sobre la palabra del cierre ("Comenta la palabra"). |
| `colores` | `fondo` (cajas de subtítulos y degradados), `papel` (texto claro), `acento` y `oro` (el color de destaque principal: palabra héroe, números, resaltados). |
| `logo` | SVG o PNG con fondo transparente, de un solo color (se dibuja en blanco). Reemplaza `logo/tu-logo.svg`. |
| `fuentes` | `titulo` y `cuerpo` para los gráficos: Cinzel, Poppins, Montserrat, Playfair Display o Inter vienen incluidas (`_motor/src/fuentes.ts` explica cómo agregar otra de Google Fonts). `subtitulos` es el nombre de la fuente de los subtítulos; si no es Poppins, copia su `.ttf` a `_motor/fuentes/`. |
| `idioma` | Idioma de tus videos (`es`, `en`, `pt`…) para transcribir. |

En `ejemplos/` hay una marca completa de ejemplo (`marca-aztrotech.json` + su logo): cópiala sobre `marca.json` para ver el resultado con colores y logo reales.

Ajustes finos del ritmo, cámara y color están en `_motor/estilo.json`. Si tu app de grabación deja una línea punteada fija en el video, anota su altura relativa en `lineas_guia` y el motor la borra.

## Cómo usarlo con Claude Code

1. Pon tus videos en `01-crudos/`.
2. Abre Claude Code **dentro de la carpeta del kit** y escribe: `edita este video` (o `procesa los videos nuevos`).
3. Claude prepara el video (transcripción, mirada, cara), lee el guion, elige las tomas, escribe la edición, renderiza (1–4 min), pasa la revisión de calidad y te entrega el reel en `Entregados/<fecha>_<tema>/` con `video.mp4`, `copy.md` (título, descripción y hashtags) y `portada.jpg`.
4. Lo que quieras cambiar, se lo pides: "quita el B-roll del segundo 8", "cambia la palabra héroe". Nada se publica ni se programa sin que tú lo digas.

Sin hacerlo desde Claude Code también se puede: `python3 _motor/reel.py preparar <video>`, edita el `edicion.json` que genera y `python3 _motor/reel.py render <carpeta del proyecto>`. El formato del `edicion.json` está explicado en `skill/editor-reels/SKILL.md`.

Opcionales que mejoran el resultado (el reel se hace igual sin ellos):
- **B-roll:** pega tu `PEXELS_API_KEY` gratis en `.env` (el instalador crea el archivo; ahí viene cómo conseguirla).
- **Música:** pon tus pistas con licencia en `04-recursos/musica/` (ver su README).
- **Efectos de sonido:** descárgalos de Pixabay con los nombres de `04-recursos/sfx/README.md`.

## Consejos de grabación

- Grábate **de la cintura para arriba**, con la cara grande en cuadro. El render es más rápido (no necesita la copia 4K) y se ve mejor. Evita el plano abierto: el motor lo arregla, pero pierdes nitidez y tiempo.
- Vertical (9:16), en 4K si puedes, con la cámara a la altura de los ojos y buena luz de frente.
- Haz una pausa de un segundo antes de cada frase y repite la frase completa si te equivocas (en vez de corregirte a mitad): así los cortes caen limpios.
- Si lees un guion, no pasa nada: el motor detecta cuándo miras fuera de cámara y lo tapa. Pero mirar a la cámara siempre se ve mejor.
- Pide un reel de 25 a 45 segundos: es donde mejor funciona.

## Costos

- **Todo el motor corre en tu Mac y es gratis**: ffmpeg, Remotion, Whisper, MediaPipe y Apple Vision.
- Claude Code usa tu plan o créditos de Anthropic para decidir la edición; el motor está hecho para gastar pocos tokens (lee una transcripción compacta, no fotogramas).
- Opcional y de pago: música generada por reel (por ejemplo ElevenLabs Music, del orden de centavos de dólar por pista) o tu biblioteca de música con licencia.
- Pexels es gratis (con su llave). Pixabay es gratis.

## Licencias de terceros

El kit usa software y recursos de otros; revisa que tu uso cumpla sus licencias:

- **Remotion** (gráficos): gratis para personas y para empresas de hasta 3 empleados; las empresas más grandes necesitan una licencia de empresa. Mira https://www.remotion.dev/license antes de usar este kit en una empresa mayor.
- **Pexels** (B-roll): se descarga con tu propia llave bajo la [licencia de Pexels](https://www.pexels.com/license/). No se incluyen videos.
- **Pixabay** (efectos de sonido): [Licencia de contenido de Pixabay](https://pixabay.com/service/license-summary/): uso comercial sin atribución, pero no se pueden redistribuir los archivos sueltos. Por eso no vienen en el kit: descárgalos tú.
- **Música:** no se incluye ninguna. Usa solo pistas con licencia comercial.
- **Fuentes** (Cinzel, Poppins, Montserrat, Playfair Display, Inter): licencia SIL Open Font License 1.1.
- **MediaPipe** (modelo `face_landmarker.task` en `_motor/modelos/`): Apache-2.0.
- **mlx-whisper / Whisper** (MIT), **Simple Icons** (CC0; las marcas de los logos pertenecen a sus dueños), **Lucide** (ISC), **ffmpeg** (no se distribuye; lo instalas tú).

## Estructura

```
marca.json            tu marca (nombre, colores, logo, fuentes)
.env                  tu PEXELS_API_KEY (no se sube a ningún lado)
instalar.sh           instalador
logo/                 tu logo
01-crudos/            tus videos originales
02-proyectos/         trabajo intermedio de cada video
03-exportados/        salida directa del render
Entregados/           lo que ya pasó la revisión: video, copy y portada
04-recursos/          música, efectos, B-roll y LUT de color
_motor/               el motor (reel.py, qa.py, gráficos Remotion, Apple Vision)
skill/editor-reels/   la skill de Claude Code
ejemplos/             marca de ejemplo
```

## Si algo falla

- Corre otra vez `./instalar.sh`: arregla casi todo.
- `REEL_DEBUG=1 python3 _motor/reel.py render <proyecto>` muestra los detalles de cada corte.
- Si la revisión de calidad no pasa, el reel **no se entrega**; Claude arregla la edición y vuelve a renderizar.
- Cambia dónde se guardan los archivos pesados con la variable `REELS_CACHE`.

## Créditos

Creado por César Holguín · AztroTech.
