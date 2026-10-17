// Palabra héroe: tipografía de título enorme, en el color de destaque de la marca, que el motor coloca DETRÁS de la persona (su silueta se pone encima).
// Entra cerrando el espaciado y enfocándose; un brillo dorado la recorre; sale con un fundido corto.
import React from 'react';
import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {C, F} from './tema';

const ease = Easing.bezier(0.16, 1, 0.3, 1);

export const Heroe: React.FC<{texto: string; y: number; tam?: number}> = ({texto, y, tam}) => {
  const f = useCurrentFrame();
  const {durationInFrames: d} = useVideoConfig();
  const t = texto.toUpperCase();
  const size = tam ?? Math.min(270, Math.round(1000 / (t.length * 0.78 + 0.3)));
  const e = interpolate(f, [0, 16], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ease});
  const sale = interpolate(f, [d - 8, d], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const brillo = interpolate(f, [10, 34], [-60, 160], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic)});
  const deriva = interpolate(f, [0, d], [0, -14]);
  return <AbsoluteFill style={{opacity: e * sale}}>
    <div style={{position: 'absolute', left: 0, right: 0, top: y, display: 'flex', justifyContent: 'center',
      transform: `translateY(${deriva + (1 - e) * 30}px) scale(${0.94 + 0.06 * e})`}}>
      <div style={{fontFamily: F.titulo, fontWeight: 700, fontSize: size, lineHeight: 1, whiteSpace: 'nowrap',
        letterSpacing: `${0.38 - 0.3 * e}em`,
        backgroundImage: `linear-gradient(100deg, ${C.oro} 0%, ${C.oro} ${brillo - 18}%, ${C.oroBrillo} ${brillo}%, ${C.oro} ${brillo + 18}%, ${C.oroOscuro} 100%)`,
        WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent',
        filter: `blur(${(1 - e) * 9}px) drop-shadow(0 6px 18px rgba(var(--fondo-rgb),.55))`}}>{t}</div>
    </div>
  </AbsoluteFill>;
};
