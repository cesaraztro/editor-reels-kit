# Música

El motor mezcla una pista de fondo por reel (se agacha bajo tu voz y sube al terminar de hablar) y corta los zooms al ritmo de sus golpes.
**No incluimos pistas**: pon aquí las tuyas, con licencia para uso comercial en redes.

Opciones:
- Generar una pista instrumental por reel con ElevenLabs Music (de pago, ~USD 0.10–0.16 por pista).
- Pistas con licencia de tu biblioteca favorita (Epidemic Sound, Artlist, YouTube Audio Library, Pixabay Music, etc.).

Formatos: `.mp3`, `.wav`, `.m4a`, `.aac`, en esta carpeta o en subcarpetas. Ideal: 115–125 BPM, energética, sin voz, que dure lo que el reel (el motor la repite si es más corta).
En `edicion.json` se elige con `"musica": "carpeta/archivo.mp3"`; con `"auto"` el motor toma una de las que haya, y con `"none"` no pone música.
Si no hay ninguna, el reel se hace igual, sin música.

Anota de dónde salió cada pista (y su licencia) en un `licencias.json` aquí mismo; no se sube al repositorio.
