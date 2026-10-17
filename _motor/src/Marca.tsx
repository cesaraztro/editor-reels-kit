// Gráficos de identidad de la marca (colores, tipos de letra y logo vienen de marca.json vía ./tema):
// con movimiento premium: revelados con máscara,
// líneas que se dibujan, escalonados por letra y salidas limpias.
import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {C, F, LOGO} from './tema';

const expo = Easing.bezier(0.16, 1, 0.3, 1);
const cl = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const useSalida = (frames = 10) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  return interpolate(f, [d - frames, d], [1, 0], {...cl, easing: Easing.in(Easing.cubic)});
};

// letras que suben desde una máscara, con desenfoque que se resuelve
const Letras: React.FC<{t: string; delay?: number; paso?: number; style?: React.CSSProperties}> = ({t, delay = 0, paso = 1.2, style}) => {
  const f = useCurrentFrame();
  return <span style={{display: 'inline-block', ...style}}>
    {t.split('').map((ch, i) => {
      const p = interpolate(f - delay - i * paso, [0, 16], [0, 1], {...cl, easing: expo});
      return <span key={i} style={{display: 'inline-block', overflow: 'hidden', verticalAlign: 'bottom', paddingBottom: '0.08em'}}>
        <span style={{display: 'inline-block', transform: `translateY(${(1 - p) * 105}%)`, opacity: p,
          filter: `blur(${(1 - p) * 6}px)`, whiteSpace: 'pre'}}>{ch}</span>
      </span>;
    })}
  </span>;
};

export const Titulo: React.FC<{eyebrow: string; texto: string; y?: number; abajo?: boolean}> = ({eyebrow, texto, y = 250, abajo = false}) => {
  const f = useCurrentFrame();
  const s = useSalida(12);
  const linea = interpolate(f, [4, 26], [0, 1], {...cl, easing: expo});
  const velo = interpolate(f, [0, 12], [0, 1], {...cl, easing: expo});
  const palabras = texto.split(' ');
  return <AbsoluteFill style={{opacity: s, overflow: 'hidden'}}>
    <AbsoluteFill style={{opacity: velo, background: abajo
      ? 'linear-gradient(0deg, rgba(var(--fondo-rgb),.82) 0%, rgba(var(--fondo-rgb),.45) 28%, rgba(var(--fondo-rgb),0) 52%)'
      : `linear-gradient(180deg, rgba(var(--fondo-rgb),.80) 0%, rgba(var(--fondo-rgb),.38) ${Math.round((y + 330) / 1920 * 100 * 0.62)}%, rgba(var(--fondo-rgb),0) ${Math.round((y + 330) / 1920 * 100)}%)`}} />
    <div style={{position: 'absolute', top: y, left: 80, right: 80, textAlign: 'center', color: C.paper,
      transform: `translateY(${interpolate(f, [0, 90], [0, -10], cl)}px)`}}>
      <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 26, letterSpacing: interpolate(f, [0, 24], [22, 9], {...cl, easing: expo}),
        color: C.oro, textTransform: 'uppercase', opacity: interpolate(f, [0, 14], [0, 1], cl)}}>{eyebrow}</div>
      <div style={{height: 2, margin: '26px auto 30px', width: 220, display: 'flex', justifyContent: 'center'}}>
        <div style={{height: 2, width: `${linea * 100}%`, background: `linear-gradient(90deg, transparent, ${C.oro}, transparent)`}} />
      </div>
      <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 76, lineHeight: 1.14, textShadow: '0 4px 30px rgba(0,0,0,.45)'}}>
        {palabras.map((w, i) => <React.Fragment key={i}>
          <Letras t={w} delay={2 + i * 2} paso={0.45} />{i < palabras.length - 1 ? ' ' : ''}
        </React.Fragment>)}
      </div>
    </div>
  </AbsoluteFill>;
};

export const Firma: React.FC<{nombre: string; rol: string}> = ({nombre, rol}) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  const entra = interpolate(f, [0, 18], [0, 1], {...cl, easing: expo});
  const sale = interpolate(f, [d - 12, d], [0, 1], {...cl, easing: Easing.in(Easing.cubic)});
  const regla = interpolate(f, [0, 14], [0, 1], {...cl, easing: expo});
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 64, top: 1110, display: 'flex', alignItems: 'stretch',
      clipPath: `inset(0 ${(1 - entra) * 100}% 0 ${sale * 100}%)`}}>
      <div style={{background: 'linear-gradient(90deg, rgba(var(--fondo-rgb),.86), rgba(var(--fondo-rgb),.62))', padding: '22px 34px 22px 28px',
        borderRadius: 6, display: 'flex', gap: 22, boxShadow: '0 18px 40px rgba(0,0,0,.28)'}}>
        <div style={{width: 3, background: C.oro, transform: `scaleY(${regla})`, transformOrigin: 'top', borderRadius: 2}} />
        <div>
          <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 44, color: C.paper, lineHeight: 1.1}}><Letras t={nombre} delay={1} paso={0.7} /></div>
          <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 22, letterSpacing: 5, color: C.oro, textTransform: 'uppercase', marginTop: 8,
            opacity: interpolate(f, [16, 30], [0, 1], cl), transform: `translateX(${interpolate(f, [16, 30], [-14, 0], {...cl, easing: expo})}px)`}}>{rol}</div>
        </div>
      </div>
    </div>
  </AbsoluteFill>;
};

export const Tarjeta: React.FC<{num?: number; texto: string}> = ({num, texto}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = useSalida(10);
  const n = spring({frame: f, fps, config: {damping: 14, stiffness: 170, mass: 0.7}});
  const sub = interpolate(f, [8, 26], [0, 1], {...cl, easing: expo});
  return <AbsoluteFill style={{opacity: s}}>
    <AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(var(--fondo-rgb),.72) 0%, rgba(var(--fondo-rgb),.26) 26%, rgba(var(--fondo-rgb),0) 40%)',
      opacity: interpolate(f, [0, 10], [0, 1], cl)}} />
    <div style={{position: 'absolute', top: 230, left: 84, right: 84, display: 'flex', alignItems: 'center', gap: 34}}>
      {num != null && <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 150, lineHeight: 1, color: C.oro,
        transform: `scale(${0.6 + 0.4 * n}) translateY(${(1 - n) * 30}px)`, opacity: Math.min(1, n * 1.5),
        textShadow: `0 0 ${30 * (1 - sub)}px ${C.oro}88`}}>{String(num).padStart(2, '0')}</div>}
      <div style={{flex: 1, borderLeft: num != null ? `2px solid ${C.paper}55` : 'none', paddingLeft: num != null ? 34 : 0}}>
        <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 50, lineHeight: 1.18, color: C.paper, textShadow: '0 3px 20px rgba(0,0,0,.5)',
          textAlign: num != null ? 'left' : 'center'}}>
          {texto.split(' ').map((w, i) => {
            const p = interpolate(f - 6 - i * 2, [0, 14], [0, 1], {...cl, easing: expo});
            return <span key={i} style={{display: 'inline-block', marginRight: '0.28em', opacity: p, transform: `translateY(${(1 - p) * 26}px)`}}>{w}</span>;
          })}
        </div>
        <div style={{height: 3, background: C.oro, width: `${sub * 120}px`, marginTop: 16, borderRadius: 2}} />
      </div>
    </div>
  </AbsoluteFill>;
};

export const Cierre: React.FC<{texto: string; palabra: string; y?: number; compacto?: boolean}> = ({texto, palabra, y = 230, compacto = false}) => {
  const k = compacto ? 0.72 : 1;
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const velo = interpolate(f, [0, 14], [0, 1], {...cl, easing: expo});
  const pal = spring({frame: f - 8, fps, config: {damping: 16, stiffness: 150}});
  // "press": la palabra se hunde y regresa con un pulso dorado
  const press = f > 26 ? 1 - 0.06 * Math.sin(Math.min(1, (f - 26) / 9) * Math.PI) : 1;
  const pulso = interpolate(f, [26, 34, 52], [0, 1, 0], cl);
  const lg = interpolate(f, [18, 40], [0, 1], {...cl, easing: expo});
  const linea = interpolate(f, [30, 50], [0, 1], {...cl, easing: expo});
  return <AbsoluteFill style={{overflow: 'hidden'}}>
    <AbsoluteFill style={{opacity: velo, background: 'linear-gradient(180deg, rgba(var(--fondo-rgb),.82) 0%, rgba(var(--fondo-rgb),.32) 32%, rgba(var(--fondo-rgb),0) 48%)'}} />
    <div style={{position: 'absolute', top: y, left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 * k}}>
      <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 30 * k, letterSpacing: interpolate(f, [0, 22], [18, 8], {...cl, easing: expo}) * k,
        color: C.paper, textTransform: 'uppercase', opacity: velo}}>{texto}</div>
      <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 112 * k, letterSpacing: 10 * k, color: C.oro, opacity: Math.min(1, pal * 1.4),
        transform: `scale(${(0.86 + 0.14 * pal) * press})`, textShadow: `0 4px 30px rgba(0,0,0,.4), 0 0 ${50 * pulso}px ${C.oro}`}}>{palabra}</div>
      <div style={{height: 2, width: `${linea * 260}px`, background: `linear-gradient(90deg, transparent, ${C.oro}, transparent)`}} />
      <Img src={LOGO.src} style={{width: 290 * k, marginTop: 6 * k, filter: `brightness(0) invert(1) blur(${(1 - lg) * 8}px)`,
        opacity: 0.92 * lg, transform: `scale(${0.9 + 0.1 * lg})`}} />
    </div>
  </AbsoluteFill>;
};

// destello cálido de luz (light leak) para transiciones clave; sutil y en colores de la marca
export const Destello: React.FC<{lado?: string}> = ({lado = 'izq'}) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  const a = interpolate(f, [0, d * 0.35, d], [0, 0.55, 0], {...cl, easing: Easing.inOut(Easing.sin)});
  const x = interpolate(f, [0, d], lado === 'izq' ? [-20, 60] : [120, 40]);
  return <AbsoluteFill style={{opacity: a,
    background: `radial-gradient(ellipse 60% 45% at ${x}% 30%, rgba(var(--oro-brillo-rgb),.75) 0%, rgba(var(--oro-rgb),.35) 40%, rgba(var(--oro-rgb),0) 70%),
                 radial-gradient(ellipse 40% 30% at ${x + 25}% 70%, rgba(var(--oro-rgb),.35) 0%, rgba(var(--oro-rgb),0) 70%)`}} />;
};
