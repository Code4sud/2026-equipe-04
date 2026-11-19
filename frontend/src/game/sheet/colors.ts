/**
 * Pastille de la couleur préférée. Ces teintes sont la réponse du jeune, pas des couleurs
 * d'interface : elles restent hors de tokens.css. Le nom de la couleur est toujours écrit à côté.
 */
const NAMED: Record<string, string> = {
  'bleu marine': '#1f3a68',
  'bleu nuit': '#1b2a4a',
  'bleu ciel': '#8ecdf2',
  'bleu roi': '#2a4fd6',
  'bleu canard': '#14707a',
  'bleu electrique': '#2c6cff',
  bleu: '#4d8fd6',
  'vert d eau': '#9fd8c6',
  'vert pomme': '#8cc63f',
  'vert sapin': '#1f5c3a',
  'vert olive': '#7a7a32',
  'vert fluo': '#7cf03c',
  vert: '#4f9a55',
  turquoise: '#2ec4c0',
  cyan: '#33c6e0',
  emeraude: '#1f9e6e',
  menthe: '#98e0c0',
  kaki: '#8a8a4a',
  olive: '#7a7a32',
  rouge: '#d64541',
  bordeaux: '#7a1f2b',
  cerise: '#c21f3a',
  framboise: '#c72c5a',
  rose: '#f08cb3',
  'rose pale': '#f7c6d6',
  fuchsia: '#d6338a',
  magenta: '#c2289a',
  violet: '#8a5cc7',
  mauve: '#b48cc8',
  lilas: '#c8a8e0',
  lavande: '#b6a6e0',
  indigo: '#4b3fa3',
  prune: '#6b2f5b',
  orange: '#f08a3c',
  abricot: '#f8a96b',
  corail: '#f2785c',
  saumon: '#f4a08a',
  peche: '#ffbe98',
  jaune: '#f7c948',
  moutarde: '#c9a227',
  ocre: '#c88a2c',
  or: '#d4a52c',
  dore: '#d4a52c',
  marron: '#7b4a2a',
  brun: '#6b4226',
  chocolat: '#5a3420',
  caramel: '#b8743a',
  beige: '#e3cfa9',
  creme: '#f6ebd2',
  noir: '#1d1b1a',
  blanc: '#ffffff',
  gris: '#9a9a9a',
  argent: '#c4c7cc',
  argente: '#c4c7cc',
};

const NAMES = Object.keys(NAMED);

function normalize(text: string) {
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z]+/g, ' ');
}

/** Teinte reconnue dans la réponse (« Bleu marine », « le vert »…), ou null. */
export function swatchFor(value: string): string | null {
  const text = ` ${normalize(value)} `;
  let best: { index: number; name: string } | null = null;
  for (const name of NAMES) {
    const index = text.indexOf(` ${name} `);
    if (index < 0) continue;
    if (!best || index < best.index || (index === best.index && name.length > best.name.length)) {
      best = { index, name };
    }
  }
  return best ? NAMED[best.name] : null;
}

/** Un détail qui parle de couleur reçoit une pastille. */
export function isColorFact(fact: { key: string; label: string }) {
  return /couleur/i.test(fact.key) || /couleur/i.test(normalize(fact.label));
}
