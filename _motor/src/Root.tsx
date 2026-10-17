// Gráficos con fondo transparente. El motor los renderiza por separado (solo su duración)
// y ffmpeg los superpone sobre el video. Estilo premium; colores, tipos de letra y logo salen de marca.json
// (reel.py los manda en la prop `marca`; ver ./tema.ts).
import React, {useEffect, useState} from 'react';
import {AbsoluteFill, Composition, continueRender, delayRender, interpolate, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {C, F, aplicarMarca, fuentesRequeridas, varsCss} from './tema';
import {Escena} from './Escena';
import {Pop, Barra} from './Pop';
import {Heroe} from './Heroe';
import {Titulo, Firma, Tarjeta, Cierre, Destello} from './Marca';
// plantillas nuevas (en prueba, 2026-10-11)
import {Duelo} from './Duelo';
import {Explicador} from './Explicador';

const ease = Easing.bezier(0.22, 1, 0.36, 1);

// entrada / salida suaves (0→1→0)
const useVida = (entrada = 14, salida = 12) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  const i = interpolate(f, [0, entrada], [0, 1], {extrapolateRight: 'clamp', easing: ease});
  const o = interpolate(f, [d - salida, d], [1, 0], {extrapolateLeft: 'clamp', easing: ease});
  return Math.min(i, o);
};

const Revela: React.FC<{children: React.ReactNode; delay?: number; style?: React.CSSProperties}> = ({children, delay = 0, style}) => {
  const f = useCurrentFrame();
  const p = interpolate(f - delay, [0, 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  return <div style={{overflow: 'hidden', ...style}}><div style={{transform: `translateY(${(1 - p) * 105}%)`, opacity: p}}>{children}</div></div>;
};

// Inserto a pantalla completa: cubre el instante en que la persona lee; muestra la frase que dice
export const Frase: React.FC<{texto: string}> = ({texto}) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  const v = Math.min(interpolate(f, [0, 5], [0, 1], {extrapolateRight: 'clamp'}), interpolate(f, [d - 5, d], [1, 0], {extrapolateLeft: 'clamp'}));
  const luz = interpolate(f, [0, d], [30, 70]);
  const palabras = texto.split(' ');
  return <AbsoluteFill style={{opacity: v, background: `radial-gradient(circle at ${luz}% 35%, var(--fondo-2) 0%, ${C.navy} 55%, var(--fondo-0) 100%)`,
    justifyContent: 'center', alignItems: 'center', padding: 90}}>
    <div style={{height: 2, width: 120, background: C.oro, marginBottom: 46, transform: `scaleX(${interpolate(f, [0, 12], [0, 1], {extrapolateRight: 'clamp', easing: ease})})`}} />
    <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '8px 22px'}}>
      {palabras.map((w, i) => <Revela key={i} delay={i * 2}><span style={{fontFamily: F.titulo, fontWeight: 700, fontSize: palabras.length > 6 ? 72 : 92, lineHeight: 1.15, color: C.paper}}>{w}</span></Revela>)}
    </div>
  </AbsoluteFill>;
};

// Cada composición recibe la prop `marca` (colores, fuentes, logo). Se aplica antes de dibujar, se exponen
// los colores como variables CSS y se espera a que las fuentes estén cargadas antes de capturar cuadros.
const ConMarca = (Componente: any) => (props: any) => {
  aplicarMarca(props.marca);
  const [h] = useState(() => delayRender('fuentes de la marca'));
  useEffect(() => {
    const fu = (document as any).fonts;
    Promise.all(fuentesRequeridas().map((x) => fu.load(x))).catch(() => null).then(() => fu.ready).then(() => continueRender(h));
  }, [h]);
  return <AbsoluteFill style={varsCss() as React.CSSProperties}><Componente {...props} /></AbsoluteFill>;
};

const envueltos = new Map<string, any>();
const comp = (id: string, component: any, defaultProps: any) =>
  <Composition key={id} id={id} component={envueltos.get(id) ?? (envueltos.set(id, ConMarca(component)), envueltos.get(id))} width={1080} height={1920} fps={30} durationInFrames={90} defaultProps={defaultProps}
    calculateMetadata={({props}: any) => ({durationInFrames: Math.max(15, Math.round((props.duracion ?? 3) * 30))})} />;

export const Root: React.FC = () => <>
  {comp('Titulo', Titulo, {eyebrow: 'TuMarca', texto: 'Título'})}
  {comp('Firma', Firma, {nombre: 'Nombre', rol: 'Rol'})}
  {comp('Tarjeta', Tarjeta, {num: 1, texto: 'Texto'})}
  {comp('Frase', Frase, {texto: 'Frase'})}
  {comp('Escena', Escena, {tipo: 'icono', texto: 'Texto', iconos: ['users']})}
  {comp('Cierre', Cierre, {texto: 'Comenta la palabra', palabra: 'EQUIPO'})}
  {comp('Pop', Pop, {tipo: 'logo', iconos: ['si:n8n']})}
  {comp('Barra', Barra, {items: [{icono: 'si:n8n', at: 0}]})}
  {comp('Heroe', Heroe, {texto: 'ESCALAR', y: 520})}
  {comp('Destello', Destello, {lado: 'izq'})}
  {comp('Duelo', Duelo, {
    pedido: 'Contesta este WhatsApp: “Quiero cancelar. Llevo dos días esperando respuesta.”',
    a: {nombre: 'Claude', texto: 'Tienes toda la razón y te pido una disculpa: dos días es demasiado. Antes de que canceles, déjame resolverlo hoy mismo. ¿Me compartes tu número de pedido?'},
    b: {nombre: 'ChatGPT', texto: 'Lamentamos los inconvenientes. Su solicitud de cancelación ha sido recibida y será procesada a la brevedad.'},
    ganador: 'a', fondo: 'navy', duracion: 8})}
  {comp('Explicador', Explicador, {
    titular: 'Tu titular aquí', eyebrow: 'Tu etiqueta', duracion: 8,
    beats: [
      {t: 0.4, tipo: 'contador', valor: 25, prefijo: '$', sufijo: 'USD', etiqueta: 'una cifra que enganche'},
      {t: 2.4, tipo: 'texto', texto: 'Una frase corta y clara.'},
      {t: 4.2, tipo: 'lista', items: ['Primer punto', 'Segundo punto', 'Tercer punto']},
      {t: 6.2, tipo: 'logos', texto: 'Las herramientas', logos: ['claude', 'chatgpt', 'gemini', 'notion', 'whatsapp']},
    ]})}
</>;
