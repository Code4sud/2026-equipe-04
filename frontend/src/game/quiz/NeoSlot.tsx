export type NeoMood = 'happy' | 'thinking' | 'cheer' | 'wave';

/** Emplacement de Néo, le renard 3D : l'intégration remplacera cette pastille par le modèle. */
export function NeoSlot({ mood }: { mood: NeoMood }) {
  return <div className="neo-slot" data-mood={mood} aria-hidden="true" />;
}
