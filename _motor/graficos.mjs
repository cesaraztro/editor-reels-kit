// Renderiza gráficos con alfa (ProRes 4444) en un solo bundle. Caché por hash de props.
//   node graficos.mjs lista.json   -> lista: [{comp, props, out}]
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';

const lista = JSON.parse(fs.readFileSync(process.argv[2], 'utf8')).filter((g) => !fs.existsSync(g.out));
if (!lista.length) { console.log('gráficos: todo en caché'); process.exit(0); }
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
await Promise.all(lista.map(async (g) => {
  const composition = await selectComposition({serveUrl, id: g.comp, inputProps: g.props});
  const tmp = g.out + '.tmp.mov';
  await renderMedia({composition, serveUrl, codec: 'prores', proResProfile: '4444', pixelFormat: 'yuva444p10le',
    imageFormat: 'png', outputLocation: tmp, inputProps: g.props, concurrency: 2, logLevel: 'error'});
  fs.renameSync(tmp, g.out);
}));
console.log(`gráficos: ${lista.length} renderizados`);
