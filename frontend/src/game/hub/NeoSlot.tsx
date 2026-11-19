import { NeoAvatar, type NeoMood } from '../neo/NeoAvatar';
import './common.css';

export type { NeoMood };

/** Néo dans le hub et les écrans de partie : en 3D, sauf `still` (chargements, messages). */
export function NeoSlot({ mood, still = false }: { mood: NeoMood; still?: boolean }) {
  return <NeoAvatar mood={mood} still={still} className="neo-slot" />;
}
