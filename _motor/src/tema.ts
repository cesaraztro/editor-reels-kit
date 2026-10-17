// Tema de marca de los gráficos. reel.py lee marca.json y lo manda como prop `marca` a cada composición;
// Root.tsx llama a aplicarMarca() antes de dibujar. Aquí quedan los valores por defecto (genéricos).
//   C  -> colores (se leen al dibujar, no al importar: por eso es un objeto que se actualiza)
//   F  -> tipos de letra  {titulo, cuerpo}
//   LOGO.src -> logo como data URI
//   varsCss() -> variables CSS (--fondo, --oro-rgb…) para usar rgba(var(--fondo-rgb), .8) en los estilos
import './fuentes';

export type MarcaProps = {
  colores?: {fondo?: string; papel?: string; acento?: string; oro?: string};
  fuentes?: {titulo?: string; cuerpo?: string};
  logo?: string;
};

const hex2rgb = (h: string): [number, number, number] => {
  const x = h.replace('#', '');
  return [parseInt(x.slice(0, 2), 16), parseInt(x.slice(2, 4), 16), parseInt(x.slice(4, 6), 16)];
};
const rgb2hex = (c: number[]) => '#' + c.map((v) => Math.round(Math.min(255, Math.max(0, v))).toString(16).padStart(2, '0')).join('').toUpperCase();
// mezcla a con b (t = 0..1 de b)
export const mezcla = (a: string, b: string, t: number) => {
  const A = hex2rgb(a), B = hex2rgb(b);
  return rgb2hex(A.map((v, i) => v + (B[i] - v) * t));
};

export const C: Record<string, string> = {};
export const F = {titulo: 'Cinzel', cuerpo: 'Poppins'};
export const LOGO = {src: ''};

const DEF = {fondo: '#14142B', papel: '#F5F5F7', acento: '#7DD3FC', oro: '#FF8A3D'};

export const aplicarMarca = (m?: MarcaProps) => {
  const c = {...DEF, ...(m?.colores ?? {})};
  C.navy = c.fondo;              // fondo de marca (nombre histórico: "navy")
  C.fondo = c.fondo;
  C.paper = c.papel;
  C.papel = c.papel;
  C.acento = c.acento;
  C.azul = c.acento;
  C.oro = c.oro;                 // color de destaque principal
  C.oroClaro = mezcla(c.oro, '#FFFFFF', 0.4);
  C.oroBrillo = mezcla(c.oro, '#FFFFFF', 0.8);
  C.oroOscuro = mezcla(c.oro, '#000000', 0.15);
  C.fondo0 = mezcla(c.fondo, '#000000', 0.55);     // más oscuro que el fondo
  C.fondo1 = mezcla(c.fondo, c.acento, 0.07);      // más claro, con un toque del acento
  C.fondo2 = mezcla(c.fondo, c.acento, 0.12);
  C.fondo3 = mezcla(c.fondo, c.acento, 0.18);
  if (m?.fuentes?.titulo) F.titulo = m.fuentes.titulo;
  if (m?.fuentes?.cuerpo) F.cuerpo = m.fuentes.cuerpo;
  if (m?.logo) LOGO.src = m.logo;
};
aplicarMarca();

export const varsCss = (): Record<string, string> => {
  const v: Record<string, string> = {};
  for (const k of ['fondo', 'papel', 'acento', 'oro', 'oroClaro', 'oroBrillo', 'oroOscuro', 'fondo0', 'fondo1', 'fondo2', 'fondo3']) {
    const nombre = k.replace(/[A-Z0-9]/g, (ch) => '-' + ch.toLowerCase());
    v[`--${nombre}`] = C[k];
    v[`--${nombre}-rgb`] = hex2rgb(C[k]).join(',');
  }
  return v;
};

// tipos de letra que hay que tener cargados antes de dibujar (la renderización espera a que estén)
export const fuentesRequeridas = () =>
  [`400 40px "${F.cuerpo}"`, `600 40px "${F.cuerpo}"`, `800 40px "${F.cuerpo}"`, `700 40px "${F.titulo}"`];
