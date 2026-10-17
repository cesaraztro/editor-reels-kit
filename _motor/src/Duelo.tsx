// Plantilla "Duelo" (en prueba, 2026-10-11): la misma petición a dos IAs, estilo chat.
// Arriba la burbuja del pedido; debajo dos tarjetas apiladas (A arriba, B abajo) que se escriben solas
// al mismo tiempo y terminan juntas. Si hay ganador, al final se marca con borde oro y etiqueta "GANADOR".
// Textos largos: la letra se ajusta sola (medida real en el DOM) y, si aun así no cabe, la tarjeta hace scroll suave.
import React, {useEffect, useLayoutEffect, useRef, useState} from 'react';
import {AbsoluteFill, continueRender, delayRender, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {icons as lucide} from 'lucide-react';
import {Logo, NOMBRES} from './Logos';
import {C, F, fuentesRequeridas} from './tema';

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const cl = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// espera a que las fuentes de la marca estén cargadas antes de medir (si no, el autoajuste mide con la fuente de respaldo)
export const useFuentes = () => {
  const [h] = useState(() => delayRender('fuentes plantillas'));
  useEffect(() => {
    const f = (document as any).fonts;
    Promise.all(fuentesRequeridas().map((x) => f.load(x)))
      .catch(() => null).then(() => f.ready).then(() => continueRender(h));
  }, [h]);
};

// Texto que se escribe solo (p = 0..1). El resto va transparente para que el renglón no brinque al teclear.
// Ajusta el tamaño para que quepa en su caja; si ni con `min` cabe, hace scroll suave siguiendo al cursor.
export const TextoVivo: React.FC<{texto: string; p: number; max: number; min: number; cursor?: boolean;
  style?: React.CSSProperties}> = ({texto, p, max, min, cursor = true, style}) => {
  const f = useCurrentFrame();
  const caja = useRef<HTMLDivElement>(null), txt = useRef<HTMLDivElement>(null);
  const [m, setM] = useState({fs: max, d: 0, p0: 1});
  // mide solo cuando las fuentes ya cargaron y la caja tiene tamaño; hasta entonces Remotion espera
  const [listo, setListo] = useState(false);
  const [h] = useState(() => delayRender('TextoVivo'));
  useEffect(() => {
    const fu = (document as any).fonts;
    Promise.all(fuentesRequeridas().slice(0, 3).map((x) => fu.load(x)))
      .catch(() => null).then(() => fu.ready).then(() => setListo(true));
  }, []);
  useEffect(() => { if (listo) continueRender(h); }, [listo, h]);
  useLayoutEffect(() => {
    const b = caja.current, t = txt.current;
    if (!listo || !b || !t || b.clientHeight < 10) return;
    let s = max;
    t.style.fontSize = `${s}px`;
    while (s > min && t.scrollHeight > b.clientHeight) { s -= 1; t.style.fontSize = `${s}px`; }
    const d = Math.max(0, t.scrollHeight - b.clientHeight);
    const p0 = Math.min(0.95, (b.clientHeight * 0.72) / Math.max(1, t.scrollHeight));
    if (s !== m.fs || Math.abs(d - m.d) > 0.5 || Math.abs(p0 - m.p0) > 0.001) setM({fs: s, d, p0});
  }, [f, texto, max, min, listo]);
  const chars = Array.from(texto);
  const k = Math.round(Math.max(0, Math.min(1, p)) * chars.length);
  const off = listo && m.d > 0 ? m.d * interpolate(p, [m.p0, 1], [0, 1], cl) : 0;
  const parpadeo = p >= 1 ? (Math.floor(f / 15) % 2 === 0 ? 1 : 0) : 1;
  return <div ref={caja} style={{position: 'relative', overflow: 'hidden', flex: 1, minHeight: 0,
    maskImage: m.d > 0 && off > 2 ? 'linear-gradient(180deg, transparent 0, #000 14%)' : undefined,
    WebkitMaskImage: m.d > 0 && off > 2 ? 'linear-gradient(180deg, transparent 0, #000 14%)' : undefined}}>
    <div ref={txt} style={{fontSize: m.fs, lineHeight: 1.36, transform: `translateY(${-off}px)`, whiteSpace: 'pre-wrap',
      overflowWrap: 'break-word', ...style}}>
      <span>{chars.slice(0, k).join('')}</span>
      {cursor && p > 0 && <span style={{display: 'inline-block', height: '1.05em', verticalAlign: '-0.18em', borderLeft: `3px solid ${C.oro}`,
        marginLeft: -1.5, marginRight: -1.5, opacity: parpadeo}} />}
      <span style={{color: 'transparent'}}>{chars.slice(k).join('')}</span>
    </div>
  </div>;
};

// tres puntos de "escribiendo…"
const Pensando: React.FC<{color?: string}> = ({color = C.paper}) => {
  const f = useCurrentFrame();
  return <div style={{display: 'flex', gap: 12, paddingTop: 10}}>
    {[0, 1, 2].map((i) => <div key={i} style={{width: 16, height: 16, borderRadius: 8, background: color,
      opacity: 0.35 + 0.65 * Math.max(0, Math.sin((f - i * 5) / 5)), transform: `translateY(${-6 * Math.max(0, Math.sin((f - i * 5) / 5))}px)`}} />)}
  </div>;
};

type Lado = {nombre: string; texto: string; icono?: string};

const Tarjeta: React.FC<{lado: Lado; etiqueta: string; p: number; entra: number; pensando: boolean; gana: number; pierde: number}> =
  ({lado, etiqueta, p, entra, pensando, gana, pierde}) => {
  const Trofeo = (lucide as any).Trophy;
  const nombre = NOMBRES[lado.nombre.toLowerCase().replace(/[^a-z0-9]/g, '')] ?? lado.nombre;
  return <div style={{flex: 1, minHeight: 0, position: 'relative', opacity: entra * (1 - 0.5 * pierde),
    transform: `translateY(${(1 - entra) * 60}px) scale(${1 + 0.025 * gana - 0.03 * pierde})`, filter: `saturate(${1 - 0.6 * pierde})`}}>
    <div style={{position: 'absolute', inset: 0, borderRadius: 34, padding: '30px 40px 34px', display: 'flex', flexDirection: 'column',
      background: 'linear-gradient(160deg, rgba(var(--fondo-2-rgb),.94) 0%, rgba(var(--fondo-rgb),.96) 70%)',
      border: `${2 + 2 * gana}px solid ${gana > 0 ? `rgba(var(--oro-rgb),${0.15 + 0.85 * gana})` : 'rgba(var(--papel-rgb),.12)'}`,
      boxShadow: `0 30px 70px rgba(0,0,0,.45), 0 0 ${60 * gana}px rgba(var(--oro-rgb),${0.45 * gana}), inset 0 1px 0 rgba(255,255,255,.08)`}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 26}}>
        <Logo nombre={lado.icono ?? lado.nombre} size={88} />
        <div>
          <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 21, letterSpacing: 6, color: C.oro, textTransform: 'uppercase'}}>{etiqueta}</div>
          <div style={{fontFamily: F.cuerpo, fontWeight: 800, fontSize: 60, lineHeight: 1.05, color: C.paper, letterSpacing: -0.5}}>{nombre}</div>
        </div>
      </div>
      <div style={{height: 2, margin: '24px 0 22px', background: 'linear-gradient(90deg, rgba(var(--oro-rgb),.7), rgba(var(--oro-rgb),0))'}} />
      {pensando && p <= 0
        ? <Pensando color={C.acento} />
        : <TextoVivo texto={lado.texto} p={p} max={52} min={26} style={{fontFamily: F.cuerpo, fontWeight: 400, color: C.paper}} />}
    </div>
    {gana > 0 && <div style={{position: 'absolute', top: -28, right: 36, display: 'flex', alignItems: 'center', gap: 12,
      padding: '12px 26px', borderRadius: 40, background: `linear-gradient(135deg, ${C.oroClaro}, ${C.oro})`,
      boxShadow: '0 12px 30px rgba(0,0,0,.4)', transform: `scale(${gana}) rotate(${(1 - gana) * -8}deg)`, opacity: Math.min(1, gana * 1.4)}}>
      {Trofeo && <Trofeo size={30} color={C.navy} strokeWidth={2.2} />}
      <span style={{fontFamily: F.cuerpo, fontWeight: 800, fontSize: 28, letterSpacing: 6, color: C.navy}}>GANADOR</span>
    </div>}
  </div>;
};

export const Duelo: React.FC<{pedido: string; a: Lado; b: Lado; duracion?: number; ganador?: 'a' | 'b' | null;
  fondo?: 'navy' | 'transparente'; eyebrow?: string}> = ({pedido, a, b, ganador = null, fondo = 'navy', eyebrow = 'Misma petición · dos IAs'}) => {
  useFuentes();
  const f = useCurrentFrame();
  const {fps, durationInFrames: d} = useVideoConfig();
  const T = d / fps;
  // tiempos (s): pedido → tarjetas → "pensando" → tecleo sincronizado → ganador
  const tEscribe = Math.min(1.2, T * 0.15);
  const tFin = Math.max(tEscribe + 1, T - (ganador ? 2.0 : 0.8));
  const tGana = tFin + 0.25;
  const fr = (s: number) => s * fps;
  const pA = interpolate(f, [fr(tEscribe), fr(tFin)], [0, 1], cl);
  const pB = interpolate(f, [fr(tEscribe + 0.15), fr(tFin)], [0, 1], cl);
  const burbuja = spring({frame: f - 2, fps, config: {damping: 15, stiffness: 160, mass: 0.7}});
  const entraA = interpolate(f, [fr(0.35), fr(0.35) + 16], [0, 1], {...cl, easing: ease});
  const entraB = interpolate(f, [fr(0.5), fr(0.5) + 16], [0, 1], {...cl, easing: ease});
  const g = ganador ? spring({frame: f - fr(tGana), fps, config: {damping: 12, stiffness: 150, mass: 0.7}}) : 0;
  const salida = interpolate(f, [d - 10, d], [1, 0], {...cl, easing: Easing.in(Easing.cubic)});
  const vs = spring({frame: f - fr(0.7), fps, config: {damping: 12, stiffness: 170}});
  const luz = interpolate(f, [0, d], [25, 70]);
  return <AbsoluteFill style={{opacity: salida}}>
    {fondo === 'navy' && <AbsoluteFill style={{background: `radial-gradient(circle at ${luz}% 22%, var(--fondo-2) 0%, ${C.navy} 55%, var(--fondo-0) 100%)`}} />}
    {fondo !== 'navy' && <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(var(--fondo-0-rgb),.55) 0%, rgba(var(--fondo-0-rgb),.25) 50%, rgba(var(--fondo-0-rgb),.55) 100%)'}} />}
    <div style={{position: 'absolute', top: 140, bottom: 230, left: 56, right: 56, display: 'flex', flexDirection: 'column'}}>
      <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 24, letterSpacing: interpolate(f, [0, 22], [16, 8], {...cl, easing: ease}),
        color: C.oro, textTransform: 'uppercase', textAlign: 'center', opacity: interpolate(f, [0, 12], [0, 1], cl), marginBottom: 22}}>{eyebrow}</div>
      {/* burbuja del pedido (como mensaje propio en un chat) */}
      <div style={{alignSelf: 'flex-end', maxWidth: '88%', maxHeight: 300, display: 'flex', flexDirection: 'column',
        background: C.paper, borderRadius: '34px 34px 8px 34px', padding: '24px 32px 26px', boxShadow: '0 20px 50px rgba(0,0,0,.4)',
        transform: `translateY(${(1 - burbuja) * 50}px) scale(${0.9 + 0.1 * burbuja})`, transformOrigin: 'bottom right', opacity: Math.min(1, burbuja * 1.5)}}>
        <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 20, letterSpacing: 5, color: '#5a6b82', textTransform: 'uppercase', marginBottom: 8}}>Tu pedido</div>
        <div style={{display: 'flex', maxHeight: 230}}>
          <TextoVivo texto={pedido} p={1} max={40} min={26} cursor={false} style={{fontFamily: F.cuerpo, fontWeight: 600, color: C.navy}} />
        </div>
      </div>
      <div style={{flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 44, marginTop: 44, position: 'relative'}}>
        <Tarjeta lado={a} etiqueta="Respuesta A" p={pA} entra={entraA} pensando={f >= fr(0.6)}
          gana={ganador === 'a' ? g : 0} pierde={ganador === 'b' ? g : 0} />
        <Tarjeta lado={b} etiqueta="Respuesta B" p={pB} entra={entraB} pensando={f >= fr(0.75)}
          gana={ganador === 'b' ? g : 0} pierde={ganador === 'a' ? g : 0} />
        {/* sello VS entre las dos tarjetas */}
        <div style={{position: 'absolute', left: '50%', top: '50%', width: 92, height: 92, marginLeft: -46, marginTop: -46, borderRadius: 46,
          display: 'grid', placeItems: 'center', background: C.navy, border: `2px solid ${C.oro}`, boxShadow: '0 10px 30px rgba(0,0,0,.5)',
          transform: `scale(${vs})`, opacity: Math.min(1, vs * 1.4) * (1 - g)}}>
          <span style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 34, color: C.oro, letterSpacing: 2}}>VS</span>
        </div>
      </div>
    </div>
  </AbsoluteFill>;
};
