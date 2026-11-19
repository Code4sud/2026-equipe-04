import './common.css';

export type NeoMood = 'happy' | 'thinking' | 'cheer' | 'wave';

/** Place de Néo : l’intégration remplace cette pastille par le renard 3D. */
export function NeoSlot({ mood }: { mood: NeoMood }) {
  return <div className="neo-slot" data-mood={mood} aria-hidden="true" />;
}
