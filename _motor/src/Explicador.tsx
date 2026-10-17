// Plantilla "Explicador" (en prueba, 2026-10-11) para el formato experimento
// ("Le di a Claude $25 a la semana para hacerme viral").
// Ocupa la MITAD SUPERIOR (0–960 px): panel navy con gradiente, titular fijo arriba y "beats" que se van turnando.
// El resto del cuadro es transparente: ahí va el video de la persona (desplazado a la mitad inferior).
// beats: [{t, tipo:'contador'|'texto'|'lista'|'logos', ...}]
//   contador: valor, prefijo?, sufijo?, etiqueta?, decimales?
//   texto:    texto
//   lista:    items[], titulo?
//   logos:    logos[] (claude, chatgpt, gemini, notion, whatsapp…), texto?
import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {Logo, NOMBRES} from './Logos';
import {useFuentes} from './Duelo';
import {C, F, LOGO} from './tema';

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const expo = Easing.bezier(0.16, 1, 0.3, 1);
const cl = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export type Beat = {t: number; tipo: 'contador' | 'texto' | 'lista' | 'logos'; valor?: number; prefijo?: string; sufijo?: string;
  etiqueta?: string; decimales?: number; texto?: string; items?: string[]; titulo?: string; logos?: string[]};

// palabra que sube desde una máscara
const Sube: React.FC<{children: React.ReactNode; f: number; delay?: number; style?: React.CSSProperties}> = ({children, f, delay = 0, style}) => {
  const p = interpolate(f - delay, [0, 16], [0, 1], {...cl, easing: expo});
  return <span style={{display: 'inline-block', overflow: 'hidden', verticalAlign: 'bottom', paddingBottom: '0.06em', ...style}}>
    <span style={{display: 'inline-block', transform: `translateY(${(1 - p) * 105}%)`, opacity: p, filter: `blur(${(1 - p) * 5}px)`}}>{children}</span>
  </span>;
};

const Contador: React.FC<{b: Beat; lf: number; dur: number}> = ({b, lf, dur}) => {
  const {fps} = useVideoConfig();
  const fin = Math.min(1.4, dur * 0.55) * fps;
  const k = interpolate(lf, [4, 4 + fin], [0, 1], {...cl, easing: Easing.bezier(0.2, 0.7, 0.2, 1)});
  const dec = b.decimales ?? 0;
  const n = (b.valor ?? 0) * k;
  const num = n.toLocaleString('es-MX', {minimumFractionDigits: dec, maximumFractionDigits: dec});
  const pulso = interpolate(lf, [4 + fin, 10 + fin, 26 + fin], [0, 1, 0], cl);
  const etq = interpolate(lf, [10, 26], [0, 1], {...cl, easing: expo});
  const largo = (b.prefijo ?? '').length + String(Math.round(b.valor ?? 0)).length;
  const fs = largo <= 3 ? 250 : largo <= 5 ? 200 : 150;
  return <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center'}}>
    <div style={{display: 'flex', alignItems: 'baseline', gap: 18, transform: `scale(${1 + 0.04 * pulso})`}}>
      <span style={{fontFamily: F.titulo, fontWeight: 700, fontSize: fs, lineHeight: 1, color: C.oro, fontVariantNumeric: 'tabular-nums',
        textShadow: `0 6px 40px rgba(0,0,0,.45), 0 0 ${60 * pulso}px ${C.oro}`}}>{b.prefijo ?? ''}{num}</span>
      {b.sufijo && <span style={{fontFamily: F.cuerpo, fontWeight: 800, fontSize: fs * 0.3, color: C.paper, opacity: etq}}>{b.sufijo.trim()}</span>}
    </div>
    {b.etiqueta && <div style={{marginTop: 26, fontFamily: F.cuerpo, fontWeight: 600, fontSize: 32, letterSpacing: 7, textTransform: 'uppercase',
      color: C.paper, opacity: 0.88 * etq, transform: `translateY(${(1 - etq) * 16}px)`, textAlign: 'center', maxWidth: 900}}>{b.etiqueta}</div>}
  </div>;
};

const Texto: React.FC<{b: Beat; lf: number}> = ({b, lf}) => {
  const t = b.texto ?? '';
  const fs = t.length <= 18 ? 104 : t.length <= 34 ? 84 : t.length <= 60 ? 66 : 54;
  const palabras = t.split(' ');
  return <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: fs, lineHeight: 1.16, color: C.paper, textAlign: 'center', maxWidth: 940,
    textShadow: '0 4px 30px rgba(0,0,0,.45)'}}>
    {palabras.map((w, i) => <React.Fragment key={i}><Sube f={lf} delay={i * 2.5}>{w}</Sube>{i < palabras.length - 1 ? ' ' : ''}</React.Fragment>)}
  </div>;
};

const Lista: React.FC<{b: Beat; lf: number; dur: number}> = ({b, lf, dur}) => {
  const {fps} = useVideoConfig();
  const items = b.items ?? [];
  const paso = Math.min(0.45, Math.max(0.15, (dur - 0.8) / Math.max(1, items.length))) * fps;
  const fs = items.length <= 3 ? 48 : items.length === 4 ? 42 : 36;
  return <div style={{display: 'flex', flexDirection: 'column', gap: items.length <= 3 ? 34 : 24, width: 900}}>
    {b.titulo && <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 26, letterSpacing: 8, color: C.oro, textTransform: 'uppercase',
      opacity: interpolate(lf, [0, 12], [0, 1], cl)}}>{b.titulo}</div>}
    {items.map((it, i) => {
      const p = interpolate(lf - 4 - i * paso, [0, 16], [0, 1], {...cl, easing: expo});
      return <div key={i} style={{display: 'flex', alignItems: 'center', gap: 28, opacity: p, transform: `translateX(${(1 - p) * -50}px)`,
        clipPath: `inset(-20px ${(1 - p) * 100}% -20px -20px)`}}>
        <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: fs * 0.95, color: C.oro, minWidth: fs * 1.5}}>{String(i + 1).padStart(2, '0')}</div>
        <div style={{width: 2, alignSelf: 'stretch', background: 'rgba(var(--papel-rgb),.25)'}} />
        <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: fs, lineHeight: 1.22, color: C.paper}}>{it}</div>
      </div>;
    })}
  </div>;
};

const Logos: React.FC<{b: Beat; lf: number}> = ({b, lf}) => {
  const {fps} = useVideoConfig();
  const ls = b.logos ?? [];
  const gap = 30;
  const size = Math.min(170, (940 - gap * (ls.length - 1)) / Math.max(1, ls.length) - 6);
  return <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 44}}>
    {b.texto && <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 64, color: C.paper, textAlign: 'center'}}>
      {b.texto.split(' ').map((w, i, arr) => <React.Fragment key={i}><Sube f={lf} delay={i * 2.5}>{w}</Sube>{i < arr.length - 1 ? ' ' : ''}</React.Fragment>)}
    </div>}
    <div style={{display: 'flex', gap, justifyContent: 'center'}}>
      {ls.map((l, i) => {
        const p = spring({frame: lf - 6 - i * 4, fps, config: {damping: 11, stiffness: 190, mass: 0.6}});
        const k = l.toLowerCase().replace(/[^a-z0-9]/g, '');
        return <div key={i} style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
          transform: `scale(${p}) rotate(${(1 - p) * -12}deg)`, opacity: Math.min(1, p * 1.5)}}>
          <Logo nombre={l} size={size} />
          <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 24, color: C.paper, opacity: 0.9}}>{NOMBRES[k] ?? l}</div>
        </div>;
      })}
    </div>
  </div>;
};

export const Explicador: React.FC<{titular: string; eyebrow?: string; beats: Beat[]; duracion?: number; alto?: number}> =
  ({titular, eyebrow = 'Experimento', beats = [], alto = 960}) => {
  useFuentes();
  const f = useCurrentFrame();
  const {fps, durationInFrames: d} = useVideoConfig();
  // entrada: el panel baja como cortina; salida: sube
  const abre = interpolate(f, [0, 16], [0, 1], {...cl, easing: expo});
  const cierra = interpolate(f, [d - 12, d], [0, 1], {...cl, easing: Easing.in(Easing.cubic)});
  const visible = abre * (1 - cierra);
  const luz = interpolate(f, [0, d], [20, 75]);
  const linea = interpolate(f, [8, 30], [0, 1], {...cl, easing: expo});
  const palabras = titular.split(' ');
  const fsT = titular.length <= 30 ? 66 : titular.length <= 52 ? 56 : 48;
  const orden = [...beats].sort((x, y) => x.t - y.t);
  const activo = orden.reduce((acc, b, i) => (f >= Math.round(b.t * fps) ? i : acc), -1);
  return <AbsoluteFill>
    <div style={{position: 'absolute', top: 0, left: 0, right: 0, height: alto, overflow: 'hidden',
      clipPath: `inset(0 0 ${(1 - visible) * 100}% 0)`}}>
      <AbsoluteFill style={{background: `radial-gradient(ellipse 80% 70% at ${luz}% 8%, var(--fondo-3) 0%, var(--fondo-1) 38%, ${C.navy} 68%, var(--fondo-0) 100%)`}} />
      <AbsoluteFill style={{background: `radial-gradient(ellipse 50% 35% at ${100 - luz}% 100%, rgba(var(--oro-rgb),.13) 0%, rgba(var(--oro-rgb),0) 70%)`}} />
      {/* titular fijo */}
      <div style={{position: 'absolute', top: 120, left: 70, right: 70, textAlign: 'center'}}>
        <div style={{fontFamily: F.cuerpo, fontWeight: 600, fontSize: 24, letterSpacing: interpolate(f, [0, 24], [20, 9], {...cl, easing: expo}),
          color: C.oro, textTransform: 'uppercase', opacity: interpolate(f, [4, 16], [0, 1], cl)}}>{eyebrow}</div>
        <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: fsT, lineHeight: 1.14, color: C.paper, marginTop: 18,
          textShadow: '0 4px 30px rgba(0,0,0,.45)'}}>
          {palabras.map((w, i) => <React.Fragment key={i}><Sube f={f} delay={6 + i * 2}>{w}</Sube>{i < palabras.length - 1 ? ' ' : ''}</React.Fragment>)}
        </div>
        <div style={{height: 2, margin: '28px auto 0', width: 260, display: 'flex', justifyContent: 'center'}}>
          <div style={{height: 2, width: `${linea * 100}%`, background: `linear-gradient(90deg, transparent, ${C.oro}, transparent)`}} />
        </div>
      </div>
      {/* escenario de beats */}
      {orden.map((b, i) => {
        const t0 = Math.round(b.t * fps);
        const t1 = i < orden.length - 1 ? Math.round(orden[i + 1].t * fps) : d;
        if (f < t0 || f >= t1 || i !== activo) return null;
        const lf = f - t0;
        const dur = (t1 - t0) / fps;
        const ent = interpolate(lf, [0, 14], [0, 1], {...cl, easing: ease});
        const sal = i < orden.length - 1 ? interpolate(f, [t1 - 9, t1], [0, 1], {...cl, easing: Easing.in(Easing.cubic)}) : 0;
        return <div key={i} style={{position: 'absolute', top: 430, bottom: 70, left: 70, right: 70, display: 'flex', alignItems: 'center',
          justifyContent: 'center', opacity: ent * (1 - sal), transform: `translateY(${(1 - ent) * 40 - sal * 34}px)`,
          filter: `blur(${(1 - ent) * 6 + sal * 6}px)`}}>
          {b.tipo === 'contador' && <Contador b={b} lf={lf} dur={dur} />}
          {b.tipo === 'texto' && <Texto b={b} lf={lf} />}
          {b.tipo === 'lista' && <Lista b={b} lf={lf} dur={dur} />}
          {b.tipo === 'logos' && <Logos b={b} lf={lf} />}
        </div>;
      })}
      {/* progreso: un punto por beat */}
      <div style={{position: 'absolute', bottom: 36, left: 0, right: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 14,
        opacity: interpolate(f, [10, 22], [0, 1], cl)}}>
        {orden.map((_, i) => <div key={i} style={{height: 8, borderRadius: 4, width: i === activo ? 40 : 8,
          background: i <= activo ? C.oro : 'rgba(var(--papel-rgb),.3)'}} />)}
      </div>
      <Img src={LOGO.src} style={{position: 'absolute', bottom: 26, right: 44, width: 130, opacity: 0.55, filter: 'brightness(0) invert(1)'}} />
    </div>
    {/* filo dorado que separa el panel del video */}
    <div style={{position: 'absolute', top: alto * visible - 2, left: 0, right: 0, height: 3, opacity: visible,
      background: `linear-gradient(90deg, rgba(var(--oro-rgb),0), ${C.oro} 20%, ${C.oroClaro} 50%, ${C.oro} 80%, rgba(var(--oro-rgb),0))`,
      boxShadow: '0 6px 24px rgba(0,0,0,.45)'}} />
  </AbsoluteFill>;
};
