import { NeoAvatar, type NeoMood } from '../neo/NeoAvatar';

export type { NeoMood };

/** Néo dans le quiz d'arrivée : en 3D, sauf `still` (vérification au chargement). */
export function NeoSlot({ mood, still = false }: { mood: NeoMood; still?: boolean }) {
  return <NeoAvatar mood={mood} still={still} className="neo-slot" />;
}
