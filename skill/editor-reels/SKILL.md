---
name: editor-reels
description: Edita videos hablando a cámara y los convierte en reels verticales premium con tu marca (kit "Editor de Reels"). Cortes al silencio real, sin pausas y a 1.12×; reencuadre automático desde 4K, zooms y punch-ins al ritmo de la música; profundidad con la silueta de la persona (Apple Vision), palabra héroe detrás de ella, golpe en blanco y negro, B-roll real de Pexels, emojis, firma, título y CTA que nunca tapan la cara, diseño sonoro, revisión de calidad automática y revisor independiente. Úsala SIEMPRE que el usuario diga "edita este video", "edítame el reel", "procesa los videos nuevos", "tengo videos nuevos en crudos", "hazle subtítulos/títulos/música", o suelte archivos en `01-crudos/` del kit.
---

# Editor de reels · motor v4

El motor hace el trabajo pesado (ffmpeg en bloques paralelos, Remotion solo para gráficos con transparencia, Whisper y Apple Vision locales). Tú haces lo editorial: elegir tomas, escribir un `edicion.json`, conseguir la música, revisar y entregar.

`R="__RUTA_KIT__"` (la carpeta del kit: la que contiene `marca.json`, `_motor/` y `instalar.sh`). Si esa ruta no existe (el kit se movió), usa la carpeta donde esté `marca.json`, o pregúntale al usuario y vuelve a correr `./instalar.sh`. Usa siempre comillas en las rutas.
- Motor: `"$R/_motor/reel.py"`, estilo en `"$R/_motor/estilo.json"`, revisión en `"$R/_motor/qa.py"`.
- Marca (nombre, firma, colores, logo, fuentes, CTA, idioma): `"$R/marca.json"`. **Todo lo visual de la marca sale de ahí**; no toques el código para cambiar colores.
- Carpetas: `01-crudos/` (entrada), `02-proyectos/<fecha>_<slug>/` (trabajo), `03-exportados/` (render) y `Entregados/<fecha>_<tema>/` (lo que ve el usuario).
- Recursos en `04-recursos/`: `musica/` (pistas con licencia), `sfx/pixabay/` + `sfx/sonido.json`, `broll/pexels/` + `broll/catalogo.json`, `lut/premium.cube`.
- Archivos pesados (copia 4K, máscara, bloques, caché de gráficos): `~/Movies/editor-reels-cache/` (cámbialo con la variable `REELS_CACHE`).

## Antes del primer video
1. ¿Está instalado? Deben existir `"$R/_motor/node_modules"`, `"$R/_motor/bin/matte"` y `"$R/_motor/.venv"`. Si falta algo: `cd "$R" && ./instalar.sh`.
2. Lee `"$R/marca.json"`. Si todavía dice "Tu Nombre", "TuMarca" o el logo es "TU LOGO", dile al usuario que configure su marca (nombre, rol, colores, logo) antes de editar; si te lo da, edítalo tú.
3. Sin `PEXELS_API_KEY` en `"$R/.env"` no hay B-roll; sin música ni efectos el reel se hace igual. Avísalo una vez, no insistas.

## Flujo de cada video
1. **Preparar** (gratis; ~1 min por video): `cd "$R/_motor" && python3 reel.py lote | tail -4`, o uno solo con `python3 reel.py preparar "<video>" --slug <tema>`. Hace todo esto:
   - convierte el HDR;
   - transcribe con Whisper;
   - detecta la mirada (MediaPipe) y la cara (Apple Vision, `caras.json`);
   - busca guías fijas de la app de grabación si las declaraste en `estilo.json` > `lineas_guia` (`lineas_fijas.json`, el motor las borra solo);
   - lanza en segundo plano la copia 4K y la máscara (`precalentar`).
2. **Leer** solo `transcripcion.txt`: `L07 57.5-63.5 | 👀 texto ⚠️[de 2.5s]`. 👀 significa que se nota que lee; ⚠️, que Whisper se tragó una toma repetida (el motor la recorta).
3. **Escribir `edicion.json`** siguiendo el *Criterio editorial* (abajo).
4. **Música del reel** (opcional pero recomendada). Ver *Música*.
5. **Renderizar**: `python3 reel.py render "../02-proyectos/<p>" | tail -6`. Tarda 1–4 min (más la primera vez en planos abiertos, por la copia 4K). Corre solo `qa.py`: si algo duro falla, **no entrega**. Arregla y vuelve a renderizar.
6. **Revisor independiente** (obligatorio antes de mostrarle algo al usuario): lanza un subagente `general-purpose` con `qa/hoja.jpg`, `qa/claves.jpg`, `qa/qa.json`, `timeline.json` y la *Lista premium*. No le des tu conclusión, dale el material. Corrige cada FIX y vuelve a renderizar.
7. **Entregar**: el mp4 (de `Entregados/<fecha>_<tema>/`), la duración, qué se hizo y lo que necesite decidir. **Nunca publiques ni programes nada** sin el visto bueno explícito de la persona.

## Reglas de tokens
- Lee `transcripcion.txt` y `edicion.json`, nunca el código del motor salvo para arreglarlo.
- Para revisar, usa `qa/hoja.jpg`, `qa/claves.jpg` o 3–5 fotogramas con `hstack` a 270–300 px de ancho. Nada de hojas enormes.
- Para varios videos usa `lote` con `run_in_background`.

## Qué hace el motor solo (no lo pidas en `edicion.json`)
- **Cortes precisos**:
  - Cada corte cae en el silencio real, medido por la energía de la voz cada 10 ms; nunca a media palabra.
  - Ignora el ruido de sentarse o respirar antes de la primera palabra (`arranque_real`).
  - Quita toda pausa mayor a 0.14 s.
  - Junta tramos casi contiguos (menos de 0.15 s).
  - Solo parte donde el audio confirma un silencio.
  - Velocidad 1.12 aplicada dentro del pipeline: una sola codificación, audio y video cuadrados a ±1 cuadro.
- **Cámara viva**:
  - Encuadre alterno 1.0/1.18 en cada corte notorio y empuje suave del 4.5% en cada toma.
  - Punch-ins expo-out de +9% en las palabras de `enfasis`, hasta 12 y separados 1.8 s, caídos en el beat.
  - Los tramos menores a 0.45 s heredan el encuadre (sin "plano relámpago").
  - Durante el CTA no hay punch-ins.
- **Reencuadre de planos abiertos**: si la cara ocupa menos del 8.5% del alto, encuadra a plano medio (cara al 41% de la altura, hasta 1.8×) recortando desde una copia 4K del crudo (`fuente_hd.mp4`).
- **Título y CTA nunca tapan la cara**: van arriba de la cabeza si caben, midiendo el zoom más cerrado de ese momento; si no caben, abajo de la barbilla.
- **Profundidad**: máscara de la persona con Apple Vision (`bin/matte`), fondo 8% más oscuro y suave, LUT, viñeta, grano y labios sin magenta.
- **Guías de la app de grabación**: si graban una línea punteada fija, se declara su fila en `lineas_guia` y el motor la borra.
- **Al ritmo**: detecta los beats de la música y alinea B-roll, punch-ins y pops (±0.12–0.15 s).
- **Diseño sonoro** (`sfx/sonido.json`): whoosh en el título, CTA y B-roll; pop en emojis; sparkle en logos; impacto grave en la palabra héroe y el golpe; click en tarjetas. Hay ≥0.35 s entre efectos. La música se agacha bajo la voz y sube al terminar de hablar. Volumen final −14 LUFS.
- **Gráficos de marca** (`src/Marca.tsx`, `Heroe.tsx`, `Pop.tsx`; colores, fuentes y logo de `marca.json`):
  - Título con letras que se revelan en ≤0.5 s.
  - Firma (nombre y rol de `marca.json`) en un panel del color de fondo de marca, que se mueve sola a un hueco libre de B-roll, héroe, pops y golpes.
  - CTA con la palabra que hace "press" y el logo.
  - 2 destellos de luz por reel.
  - El B-roll entra con zoom 1.12→1.0.
- **Subtítulos**: fuente de `marca.json` en caja del color de fondo de marca, máximo 4 palabras, palabras de `enfasis` en el color de destaque. Es el look base del kit: no lo cambies sin que el usuario lo pida.
- **Entrega segura**:
  - Escribe en `Entregados/<fecha>_<tema>/` con un marcador `.proyecto`.
  - Nunca pisa la carpeta de otro proyecto.
  - La versión anterior se guarda en `anteriores/<fecha-hora>/`.
  - El crudo pasa a `01-crudos/_procesados/` solo si la revisión pasa.

## `edicion.json` (formato v4)
```json
{
  "gancho": "El error que frena tus ventas",
  "eyebrow": "Para dueños de negocio",
  "lineas": ["L01","L02","L03","L04[:12]","L04[17:]","L05","L07[7:]"],
  "correcciones": {"Tu Marka": "TuMarca"},
  "enfasis": ["2026","ventas","básico","agentes","resultados","complejas"],
  "golpes": [{"linea":"L02","palabra":"encuentras","dur":1.3}],
  "heroes": [{"palabra":"agentes","linea":"L05"}],
  "broll": [
    {"palabra":"escuchado","linea":"L01","buscar":"dark abstract gold particles","dur":1.6},
    {"palabra":"charla","linea":"L04","buscar":"small business seminar audience","dur":1.8},
    {"palabra":"resultados","linea":"L04","buscar":"business team celebrating success office","dur":1.6}],
  "broll_relleno": ["entrepreneurs meeting office"],
  "pops": [{"tipo":"emoji","palabra":"verdad","linea":"L04","texto":"🚀","lado":"der"}],
  "cta": {"linea":"L07","palabra":"ENLACE","texto":"Da clic en el"},
  "musica": "mi-pista_122bpm.mp3",
  "copy": {"titulo":"…","caption":"…","hashtags":["#tumarca","…"]}
}
```
- `lineas`: recortes con `[:n]` y `[n:]`. Para quitar palabras en medio, usa dos referencias a la misma línea. Para contar índices: `python3 -c` sobre `lineas.json`, solo esa línea.
- `correcciones`: se suman a las de `marca.json`. Úsalas para nombres propios que Whisper escribe mal.
- `golpes`: **uno** por video, en la palabra más dura; ~1.3 s en blanco y negro con un punch fuerte.
- `heroes`: 1 (máximo 2). Es el sustantivo o verbo de la tesis, corto (≤9 letras). El motor elige la altura para que la cabeza tape ≤1 letra.
- `broll`: 3–6 por video. `buscar` va en inglés (2–5 palabras), con la paleta de la marca cuando sea abstracto. Usa `broll_relleno` solo si quedan uniones con lectura. Requiere `PEXELS_API_KEY`.
- `pops`: 1–2 emojis reales con carga (💀 ⚡ 🔥 🤔 ✅ ❌ 🚀 💰 📈), o logos **reales** (`si:<marca>`, de Simple Icons). Nunca en el CTA.
- `cta`: `texto` es lo que se lee arriba de la palabra; si no lo pones, usa `cta_texto` de `marca.json`.
- `musica`: ruta dentro de `04-recursos/musica/`, `"auto"` (una de las que haya) o `"none"`.
- `barra` y `lista` son opcionales: para videos de herramientas o enumeraciones.

## Criterio editorial (tomas y frases)
Quien graba suele repetir frases. Si se cuela una repetición, el reel se ve mal editado.
1. **Estructura**: gancho → problema → argumento o lista → solución/oferta → CTA. Una sola versión de cada idea.
2. **Tomas por idea**: de cada grupo queda **una**, la que esté completa, sin ⚠️ y, si se puede, sin 👀. Si todas son iguales, la **última**.
3. **Variantes distintas** ("tareas" contra "herramientas"): elige la que conecta con el CTA. **Nunca las dos.**
4. **Coherencia**: si quitas una premisa, quita también su consecuencia. Cada frase debe entenderse sola.
5. **Duración 25–45 s**. Corta en este orden: tomas repetidas → ejemplos redundantes → segundo nivel de explicación → muletillas de arranque ("Lo único que tienes que hacer es…"). **Nunca** el gancho, la tesis ni el CTA.
6. **B-roll que ilustra el sentido**:
   - plural con plural ("el doble de gente" lleva un equipo);
   - la acción con esa acción ("manualmente" lleva captura de datos);
   - **nada de texto legible ni código**;
   - nada de caras confundibles con la persona del video;
   - nunca en los primeros 3 s ni en el CTA.
   - **Cuando se dice "inteligencia artificial" o "IA": evita efectos abstractos** (partículas, redes, bokeh, "tecnología" genérica). Usa un pop `{"tipo":"usa","palabra":"inteligencia","iconos":["si:claude","si:googlegemini"],"texto":"IA"}` con logos reales. No busques "IA" en Pexels: trae tomas que no son de IA.
7. **Datos que no se inventan**: cifras, cupos, fechas, precios y nombres de producto salen del habla de la persona. Si dice un dato que contradice lo que ya sabes del negocio, no lo "corrijas" en silencio: pregunta.
8. Revisa `correcciones` para los nombres propios mal transcritos (marca, productos, lugares).
9. **`copy`**: título, caption con saltos de línea, bullets con emoji numérico, CTA y 5–8 hashtags (incluye el de la marca). Tono directo y de tú, en el idioma de `marca.json`.

## Música (una pista por reel)
La música sube la energía y fija el ritmo de los cortes. Cualquier pista con licencia para uso comercial sirve: tu biblioteca de música, YouTube Audio Library, Pixabay Music o una generada por reel.
- **Generada por reel** (opcional, de pago): con ElevenLabs Music (API, MCP o su web) pide una pista **instrumental** de `<duración del reel + 1>` segundos. Asegúrate de que la herramienta tenga activado "instrumental" / sin letra; si no, saldrá cantada.
- **Prompt en inglés**: `Instrumental, energetic modern <tono> track for a <N>-second vertical social reel. 115–125 BPM, punchy drums, driving bass, <textura>, energetic from the first second, final hit at <N-1> seconds. No vocals.` Energética y moderna, **nunca corporativa**.
- Guarda el mp3 en `04-recursos/musica/<tema>_<bpm>bpm.mp3`, anota su origen y licencia en `04-recursos/musica/licencias.json` y ponlo en `"musica"`.
- Sin música el reel se hace igual (queda solo la voz y los efectos).

## Lista premium (para el revisor independiente)
1. Gancho: título legible en ≤1 s y que no toque la cara.
2. Energía: encuadre variado, punch-ins, B-roll con ritmo; nada estático ni corporativo.
3. Reencuadre nítido, sin cortar cabeza ni manos; sin guías de la app de grabación.
4. Subtítulos legibles, en caja sólida del color de marca, sin chocar con gráficos.
5. Palabra héroe legible, detrás de la persona, que no tape la cara.
6. B-roll relevante, sin texto legible ni marcas de agua; golpe B/N de ~1.3 s.
7. CTA arriba de la cabeza y limpio; firma una vez; colores de marca (los de `marca.json`, no otros).
8. Nada barato: sin "planos relámpago", sin cortes a media palabra, 25–45 s.

## Si algo falla
- `REEL_DEBUG=1` imprime el nivel en dB de cada corte, el reencuadre y la posición del héroe.
- `REEL_FORZAR=1` entrega aunque la revisión falle: **solo** si el usuario lo pide.
- Faltan binarios, dependencias o el entorno de Python: `cd "$R" && ./instalar.sh` (es seguro repetirlo).
- La tipografía de los subtítulos (ASS) sale de `marca.json > fuentes.subtitulos`; si no es Poppins, copia su `.ttf` a `_motor/fuentes/` o instálala en el sistema. Las de los gráficos: Cinzel, Poppins, Montserrat, Playfair Display e Inter vienen incluidas (`src/fuentes.ts` explica cómo agregar otra).
- Pexels: la key va en `"$R/.env"` (`PEXELS_API_KEY=`). Sin key no hay B-roll, pero el reel se hace igual.

## Plantillas extra (experimentales)
Dos composiciones de Remotion que `reel.py` no usa; se renderizan aparte. Código en `_motor/src/Duelo.tsx`, `Explicador.tsx` y `Logos.tsx`; también leen colores, fuentes y logo de `marca.json` (pásalos como prop `marca`, igual que hace `reel.py`).
- **Duelo** (pantalla completa): la misma petición a dos IAs, estilo chat. Props: `pedido`, `a` = `{nombre, texto}`, `b` = `{nombre, texto}`, `duracion` (s), `ganador` (`"a"|"b"|null`), `fondo` (`"navy"|"transparente"`), `eyebrow` opcional. Ideal ≤350 caracteres por lado.
- **Explicador** (mitad superior, 0–960 px; el resto es transparente para poner el video debajo): props `titular`, `eyebrow`, `duracion`, `beats: [{t, tipo, …}]` con `contador` (`valor`, `prefijo`, `sufijo`, `etiqueta`), `texto`, `lista` (`items[]`) o `logos` (`logos[]`).
- **Render** (desde `_motor`): `npx remotion render src/index.ts Duelo out.mp4 --props=props.json`, o con transparencia: `node graficos.mjs lista.json` con `[{"comp":"Explicador","props":{…},"out":"…/x.mov"}]`.

## Velocidad
- **Archivos pesados fuera de carpetas sincronizadas**: la copia 4K, la máscara, los bloques y la caché de gráficos van a `~/Movies/editor-reels-cache/` (helper `pesado()`). Subir esos archivos a iCloud/Dropbox a mitad del render lo vuelve 5–10× más lento.
- **Precalentar**: `preparar` lanza `precalentar` en segundo plano (copia 4K + máscara completa). Mientras corre, escribe `edicion.json` y consigue la música. `render` lo espera solo si aún no termina.
- **Cámara**: recorta el encuadre base antes de `perspective`; procesa ~1/zb² de los píxeles y la imagen es idéntica.
- **Grabación**: los planos abiertos (cara < 8.5% del alto) obligan a usar 4K. Recomienda grabarse de la cintura para arriba, con la cara grande en cuadro.
