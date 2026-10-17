// Escenas de motion graphics a pantalla completa que tapan los cortes.
// tipo: icono | flujo | contador | contraste | iconos | marca
// iconos: "si:whatsapp" (logo de marca, Simple Icons) o "users" / "repeat" (Lucide, kebab-case)
import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {icons as lucide} from 'lucide-react';
import * as SI from 'simple-icons';
import {C, F, LOGO} from './tema';

const ease = Easing.bezier(0.22, 1, 0.36, 1);
const marcas: Record<string, any> = {};
for (const v of Object.values(SI) as any[]) if (v && v.slug) marcas[v.slug] = v;
const pascal = (s: string) => s.split(/[-_ ]/).map((x) => x.charAt(0).toUpperCase() + x.slice(1)).join('');

export const Icono: React.FC<{nombre: string; size: number; color?: string}> = ({nombre, size, color = C.paper}) => {
  if (nombre.startsWith('si:')) {
    const m = marcas[nombre.slice(3)];
    if (m) return <svg viewBox="0 0 24 24" width={size} height={size}><path d={m.path} fill={`#${m.hex}`} /></svg>;
    nombre = 'circle';
  }
  const L = (lucide as any)[pascal(nombre)] ?? (lucide as any).Sparkles;
  return <L size={size} color={color} strokeWidth={1.6} />;
};

const usePop = (delay = 0, damping = 13) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: f - delay, fps, config: {damping, stiffness: 160, mass: 0.7}});
};

const Tile: React.FC<{nombre: string; size?: number; delay?: number}> = ({nombre, size = 300, delay = 0}) => {
  const p = usePop(delay);
  const marca = nombre.startsWith('si:');
  return <div style={{width: size, height: size, borderRadius: size * 0.22, display: 'grid', placeItems: 'center',
    background: marca ? C.paper : 'rgba(var(--papel-rgb),.07)', border: `2px solid ${C.oro}88`,
    boxShadow: `0 30px 80px rgba(0,0,0,.45), inset 0 0 40px ${C.oro}22`,
    transform: `scale(${p}) rotate(${(1 - p) * -12}deg)`, opacity: Math.min(1, p * 1.4)}}>
    <Icono nombre={nombre} size={size * 0.56} color={C.paper} />
  </div>;
};

const Texto: React.FC<{t: string; delay?: number; size?: number}> = ({t, delay = 6, size = 70}) => {
  const f = useCurrentFrame();
  return <div style={{display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '6px 20px', padding: '0 80px'}}>
    {t.split(' ').map((w, i) => {
      const p = interpolate(f - delay - i * 2, [0, 14], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
      return <span key={i} style={{fontFamily: F.titulo, fontWeight: 700, fontSize: size, lineHeight: 1.15, color: C.paper,
        opacity: p, transform: `translateY(${(1 - p) * 40}px)`, display: 'inline-block'}}>{w}</span>;
    })}
  </div>;
};

const Fondo: React.FC = () => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  const x = interpolate(f, [0, d], [25, 75]);
  return <AbsoluteFill style={{background: `radial-gradient(circle at ${x}% 40%, var(--fondo-2) 0%, ${C.navy} 50%, var(--fondo-0) 100%)`}}>
    <AbsoluteFill style={{backgroundImage: `linear-gradient(${C.paper}0a 1px, transparent 1px), linear-gradient(90deg, ${C.paper}0a 1px, transparent 1px)`,
      backgroundSize: '90px 90px', transform: `translateY(${-f * 0.6}px)`, height: '120%'}} />
  </AbsoluteFill>;
};

const Anillos: React.FC = () => {
  const f = useCurrentFrame();
  return <>{[0, 1, 2].map((i) => {
    const t = ((f + i * 14) % 42) / 42;
    return <div key={i} style={{position: 'absolute', left: '50%', top: 150, width: 300, height: 300, borderRadius: '50%',
      border: `2px solid ${C.oro}`, transform: `translate(-50%,-50%) scale(${1 + t * 1.6})`, opacity: (1 - t) * 0.5}} />;
  })}</>;
};

const Contador: React.FC<{valor: string}> = ({valor}) => {
  const f = useCurrentFrame();
  const m = valor.match(/^(\D*)([\d.,]+)(.*)$/);
  const num = m ? parseFloat(m[2].replace(',', '')) : 0;
  const p = interpolate(f, [4, 30], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const v = m ? `${m[1]}${Number.isInteger(num) ? Math.round(num * p) : (num * p).toFixed(1)}${m[3]}` : valor;
  const s = usePop(2, 10);
  return <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 300, color: C.oro, lineHeight: 1, transform: `scale(${0.6 + 0.4 * s})`,
    textShadow: `0 0 60px ${C.oro}55`}}>{v}</div>;
};

const Flujo: React.FC<{a: string; b: string; medio?: string}> = ({a, b, medio = 'file-text'}) => {
  const f = useCurrentFrame();
  const linea = interpolate(f, [8, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  return <div style={{position: 'relative', width: 900, height: 300, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
    <Tile nombre={a} size={240} />
    <div style={{position: 'absolute', left: 250, right: 250, top: 148, height: 4, background: `repeating-linear-gradient(90deg, ${C.oro} 0 14px, transparent 14px 26px)`,
      transform: `scaleX(${linea})`, transformOrigin: 'left'}} />
    {[0, 1, 2].map((i) => {
      const t = ((f - 14 + i * 9) % 27) / 27;
      return f > 14 && <div key={i} style={{position: 'absolute', top: 115, left: 250 + t * 330, opacity: Math.sin(t * Math.PI)}}>
        <div style={{width: 70, height: 70, borderRadius: 16, background: C.paper, display: 'grid', placeItems: 'center'}}><Icono nombre={medio} size={40} color={C.navy} /></div>
      </div>;
    })}
    <Tile nombre={b} size={240} delay={6} />
  </div>;
};

const Contraste: React.FC<{texto: string}> = ({texto}) => {
  const [a, b] = texto.split('|').map((x) => x.trim());
  const f = useCurrentFrame();
  const tacha = interpolate(f, [12, 22], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const pb = usePop(14);
  const fila = (t: string, ok: boolean, p: number, extra?: React.ReactNode) =>
    <div style={{display: 'flex', alignItems: 'center', gap: 30, opacity: Math.min(1, p * 1.3), transform: `translateX(${(1 - p) * -80}px)`, position: 'relative'}}>
      <div style={{width: 110, height: 110, borderRadius: 30, display: 'grid', placeItems: 'center', background: ok ? C.oro : 'rgba(var(--papel-rgb),.08)'}}>
        <Icono nombre={ok ? 'check' : 'x'} size={70} color={ok ? C.navy : C.paper} /></div>
      <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: 64, color: ok ? C.oro : `${C.paper}aa`, position: 'relative'}}>{t}{extra}</div>
    </div>;
  return <div style={{display: 'flex', flexDirection: 'column', gap: 70}}>
    {fila(a, false, usePop(0), <div style={{position: 'absolute', left: 0, top: '52%', height: 5, background: '#d9534f', width: `${tacha * 100}%`}} />)}
    {b && fila(b, true, pb)}
  </div>;
};

export const Escena: React.FC<{tipo: string; texto: string; iconos?: string[]; valor?: string}> = ({tipo, texto, iconos = [], valor}) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  // transición circular de entrada y salida (wipe)
  const r = Math.min(interpolate(f, [0, 8], [0, 150], {extrapolateRight: 'clamp', easing: ease}),
    interpolate(f, [d - 7, d], [150, 0], {extrapolateLeft: 'clamp', easing: Easing.in(Easing.cubic)}));
  const ic = iconos.length ? iconos : ['sparkles'];
  let centro: React.ReactNode, textoY = 1150;
  if (tipo === 'flujo') centro = <Flujo a={ic[0]} b={ic[1] ?? 'check'} medio={ic[2]} />;
  else if (tipo === 'contador') centro = <Contador valor={valor ?? '10x'} />;
  else if (tipo === 'contraste') { centro = <Contraste texto={texto} />; textoY = -1; }
  else if (tipo === 'iconos') centro = <div style={{display: 'flex', gap: 40}}>{ic.slice(0, 4).map((n, i) => <Tile key={i} nombre={n} size={190} delay={i * 4} />)}</div>;
  else if (tipo === 'marca') centro = <Img src={LOGO.src} style={{width: 760, filter: 'brightness(0) invert(1)', transform: `scale(${0.85 + 0.15 * usePop(2, 20)})`, opacity: usePop(2, 20)}} />;
  else centro = <><Anillos /><Tile nombre={ic[0]} /></>;
  return <AbsoluteFill style={{clipPath: `circle(${r}% at 50% 45%)`}}>
    <Fondo />
    <div style={{position: 'absolute', left: 0, right: 0, top: tipo === 'contraste' ? 620 : 610, display: 'flex', justifyContent: 'center', alignItems: 'center', height: tipo === 'contraste' ? 'auto' : 300}}>{centro}</div>
    {textoY > 0 && <div style={{position: 'absolute', left: 0, right: 0, top: textoY}}><Texto t={texto} size={texto.length > 30 ? 60 : 72} /></div>}
    <div style={{position: 'absolute', left: '50%', top: 1500, width: 120, height: 3, background: C.oro, transform: 'translateX(-50%)', opacity: 0.8}} />
  </AbsoluteFill>;
};
