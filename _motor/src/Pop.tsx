// Gráficos que van ENCIMA de la persona (fondo transparente), estilo editor:
//   Pop   -> un logo tipo app que aparece junto a él (tipo "logo"), dos logos con "Usa esto:" (tipo "usa") o un emoji (tipo "emoji")
//   Barra -> logos que aparecen grandes y se van apilando en una barra lateral
// iconos: "si:n8n" (marca, Simple Icons, con su color) o "bot" (Lucide, en dorado)
import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {Icono} from './Escena';
import * as SI from 'simple-icons';
import {C, F} from './tema';

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const marcas: Record<string, any> = {};
for (const v of Object.values(SI) as any[]) if (v && v.slug) marcas[v.slug] = v;

// color de fondo del tile: el de la marca; si es muy claro, navy
const fondoMarca = (nombre: string) => {
  const m = nombre.startsWith('si:') ? marcas[nombre.slice(3)] : null;
  if (!m) return null;
  const h = m.hex as string;
  const l = (parseInt(h.slice(0, 2), 16) * 299 + parseInt(h.slice(2, 4), 16) * 587 + parseInt(h.slice(4, 6), 16) * 114) / 1000;
  return l > 200 ? C.navy : `#${h}`;
};

export const AppIcon: React.FC<{nombre: string; size: number; style?: React.CSSProperties}> = ({nombre, size, style}) => {
  const bg = fondoMarca(nombre);
  return <div style={{width: size, height: size, borderRadius: size * 0.24, display: 'grid', placeItems: 'center',
    background: bg ?? 'linear-gradient(160deg, var(--fondo-2) 0%, var(--fondo) 100%)',
    border: bg ? '2px solid rgba(255,255,255,.18)' : `2px solid ${C.oro}aa`,
    boxShadow: '0 18px 40px rgba(0,0,0,.45), inset 0 2px 0 rgba(255,255,255,.18)', ...style}}>
    {bg
      ? <svg viewBox="0 0 24 24" width={size * 0.56} height={size * 0.56}><path d={marcas[nombre.slice(3)].path} fill="#fff" /></svg>
      : <Icono nombre={nombre} size={size * 0.56} color={C.oro} />}
  </div>;
};

const usePop = (delay = 0) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: f - delay, fps, config: {damping: 11, stiffness: 190, mass: 0.6}});
};

const useSalida = (frames = 6) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  return interpolate(f, [d - frames, d], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.in(Easing.cubic)});
};

export const Pop: React.FC<{tipo: string; iconos?: string[]; texto?: string; lado?: string}> = ({tipo, iconos = [], texto = '', lado = 'izq'}) => {
  const p = usePop(0), p2 = usePop(4), s = useSalida();
  const pop = (k: number) => ({transform: `scale(${k * s}) rotate(${(1 - k) * -14}deg)`, opacity: Math.min(1, k * 1.5) * s});
  if (tipo === 'usa') {
    return <AbsoluteFill>
      <div style={{position: 'absolute', top: 820, left: 70, right: 70, display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
        <div style={pop(p)}><AppIcon nombre={iconos[0] ?? 'sparkles'} size={190} /></div>
        <div style={{fontFamily: F.cuerpo, fontWeight: 800, fontSize: 54, color: '#fff', textShadow: '0 4px 18px rgba(0,0,0,.6)', opacity: s * Math.min(1, p * 1.4)}}>{texto || 'Usa esto:'}</div>
        <div style={pop(p2)}><AppIcon nombre={iconos[1] ?? iconos[0] ?? 'sparkles'} size={190} /></div>
      </div>
    </AbsoluteFill>;
  }
  if (tipo === 'emoji') {
    return <AbsoluteFill>
      <div style={{position: 'absolute', top: 930, [lado === 'izq' ? 'left' : 'right']: 110, fontSize: 170, ...pop(p),
        filter: 'drop-shadow(0 10px 20px rgba(0,0,0,.35))'}}>{texto}</div>
    </AbsoluteFill>;
  }
  // logo junto a la cabeza
  return <AbsoluteFill>
    <div style={{position: 'absolute', top: 470, [lado === 'izq' ? 'left' : 'right']: 70, ...pop(p)}}>
      <AppIcon nombre={iconos[0] ?? 'sparkles'} size={230} />
    </div>
  </AbsoluteFill>;
};

// items: [{icono, at}] con "at" en segundos desde el inicio de la barra
export const Barra: React.FC<{items: {icono: string; at: number}[]}> = ({items}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = useSalida(8);
  return <AbsoluteFill style={{opacity: s}}>
    {items.map((it, i) => {
      const t0 = Math.round(it.at * fps);
      if (f < t0) return null;
      const entra = spring({frame: f - t0, fps, config: {damping: 11, stiffness: 190, mass: 0.6}});
      // grande junto a la cabeza 0.8 s y luego vuela a su lugar en la barra
      const viaje = interpolate(f - t0, [Math.round(0.8 * fps), Math.round(1.15 * fps)], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
      const x = interpolate(viaje, [0, 1], [70, 46]);
      const y = interpolate(viaje, [0, 1], [470, 690 + i * 118]);
      const size = interpolate(viaje, [0, 1], [230, 96]);
      return <div key={i} style={{position: 'absolute', left: x, top: y, transform: `scale(${entra})`, transformOrigin: 'top left', opacity: Math.min(1, entra * 1.5)}}>
        <AppIcon nombre={it.icono} size={size} />
      </div>;
    })}
  </AbsoluteFill>;
};
