# Efectos de sonido

El diseño sonoro del reel (whoosh en el título, pop en emojis, impacto en la palabra héroe…) está definido en `sonido.json`: cada evento del reel apunta a un archivo de `pixabay/`.
**No incluimos los archivos**: la licencia de Pixabay permite usarlos gratis en tus videos (sin atribución), pero no redistribuirlos sueltos. Descárgalos tú de https://pixabay.com/sound-effects/ y guárdalos en `04-recursos/sfx/pixabay/` con estos nombres:

| Archivo | Evento | Qué buscar en Pixabay |
|---|---|---|
| `whoosh-cinematic.mp3` | título y cierre | "cinematic whoosh", "whoosh transition" (≈2–3 s) |
| `whoosh-short.mp3` | B-roll | "whoosh short", "swish" (<0.7 s) |
| `click-soft.mp3` | firma | "soft click", "ui click soft" (<0.5 s) |
| `click.mp3` | tarjetas | "ui click", "button click" (<0.5 s) |
| `pop.mp3` | emojis | "pop", "bubble pop" (<0.6 s) |
| `sparkle.mp3` | logos | "sparkle", "magic shimmer" (≈1 s) |
| `impact-bass-1.mp3` | palabra héroe | "bass impact", "cinematic hit" |
| `impact-bass-2.mp3` | golpe en blanco y negro | "bass drop impact", "deep hit" |

Puedes usar otros nombres: solo cambia la ruta en `sonido.json`. `db` es el volumen del efecto y `antes`, cuántos segundos se adelanta al gráfico.
Si falta un archivo, ese efecto simplemente no suena; el reel se hace igual.
