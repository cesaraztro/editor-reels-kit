// Logos de marca para las plantillas nuevas (Duelo, Explicador). Solo agrega: reutiliza AppIcon de Pop.tsx.
// Acepta nombres sueltos ("claude", "gemini", "chatgpt", "notion", "whatsapp") o "si:<slug>" de Simple Icons.
// Si la marca no está en Simple Icons (OpenAI/ChatGPT se retiró de la librería por marca registrada),
// se dibuja un monograma con el mismo formato de tile.
import React from 'react';
import * as SI from 'simple-icons';
import {AppIcon} from './Pop';
import {F} from './tema';

const marcas: Record<string, any> = {};
for (const v of Object.values(SI) as any[]) if (v && v.slug) marcas[v.slug] = v;

const ALIAS: Record<string, string> = {
  claude: 'claude', anthropic: 'anthropic', gemini: 'googlegemini', googlegemini: 'googlegemini',
  notion: 'notion', whatsapp: 'whatsapp', n8n: 'n8n', elevenlabs: 'elevenlabs', perplexity: 'perplexity',
  make: 'make', zapier: 'zapier', instagram: 'instagram', tiktok: 'tiktok', youtube: 'youtube',
};
// sin logo disponible: monograma con color propio
const MONO: Record<string, {txt: string; bg: string}> = {
  chatgpt: {txt: 'GPT', bg: '#10A37F'}, openai: {txt: 'AI', bg: '#10A37F'}, gpt: {txt: 'GPT', bg: '#10A37F'},
  metricool: {txt: 'M', bg: '#1E6FD9'}, copilot: {txt: 'CP', bg: '#2B63D9'},
};
export const NOMBRES: Record<string, string> = {
  claude: 'Claude', anthropic: 'Anthropic', gemini: 'Gemini', googlegemini: 'Gemini', chatgpt: 'ChatGPT', openai: 'OpenAI',
  gpt: 'ChatGPT', notion: 'Notion', whatsapp: 'WhatsApp', n8n: 'n8n', elevenlabs: 'ElevenLabs', perplexity: 'Perplexity',
  make: 'Make', zapier: 'Zapier', instagram: 'Instagram', tiktok: 'TikTok', youtube: 'YouTube', metricool: 'Metricool',
};

const clave = (nombre: string) => nombre.toLowerCase().replace(/^si:/, '').replace(/[^a-z0-9]/g, '');

// devuelve "si:<slug>" si hay logo real, o null
export const slugDe = (nombre: string): string | null => {
  const k = clave(nombre);
  if (marcas[k]) return `si:${k}`;
  for (const a of Object.keys(ALIAS)) if (k.includes(a) && marcas[ALIAS[a]]) return `si:${ALIAS[a]}`;
  return null;
};

export const Logo: React.FC<{nombre: string; size: number; style?: React.CSSProperties}> = ({nombre, size, style}) => {
  const s = slugDe(nombre);
  if (s) return <AppIcon nombre={s} size={size} style={style} />;
  const k = clave(nombre);
  const m = MONO[Object.keys(MONO).find((x) => k.includes(x)) ?? ''] ?? {txt: nombre.slice(0, 2).toUpperCase(), bg: 'var(--fondo-2)'};
  return <div style={{width: size, height: size, borderRadius: size * 0.24, display: 'grid', placeItems: 'center', background: m.bg,
    border: '2px solid rgba(255,255,255,.18)', boxShadow: '0 18px 40px rgba(0,0,0,.45), inset 0 2px 0 rgba(255,255,255,.18)', ...style}}>
    <span style={{fontFamily: F.cuerpo, fontWeight: 800, fontSize: size * (m.txt.length > 2 ? 0.3 : 0.4), color: '#fff', letterSpacing: size * 0.01}}>{m.txt}</span>
  </div>;
};
