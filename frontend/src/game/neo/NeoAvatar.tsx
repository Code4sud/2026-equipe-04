import { useEffect, useRef } from 'react';
import type { MoodName } from '../../mascot/clips';
import { Mascot, type MascotHandle } from '../../mascot/Mascot';
import cheer from './neo-cheer.webp';
import happy from './neo-happy.webp';
import thinking from './neo-thinking.webp';
import wave from './neo-wave.webp';
import './neo.css';

export type NeoMood = 'happy' | 'thinking' | 'cheer' | 'wave';

/**
 * Poses fixes de Néo, rendues depuis le même modèle (frontend/src/mascot/neo.glb) : cadrage
 * « portrait » de stage.ts en mouvement réduit, recadré sur la tête, en WebP transparent.
 */
export const NEO_STILLS: Record<NeoMood, string> = { happy, thinking, cheer, wave };

/** État de fond de la 3D, et geste joué une fois à l'arrivée (voir mascot/clips.ts). */
const MOODS: Record<NeoMood, { base: MoodName; gesture?: MoodName }> = {
  happy: { base: 'idle' },
  thinking: { base: 'think' },
  cheer: { base: 'idle', gesture: 'cheer' },
  wave: { base: 'idle', gesture: 'greet' },
};

interface Props {
  mood: NeoMood;
  /** Image fixe seulement : petites places, chargements, pendant un jeu chronométré. */
  still?: boolean;
  className?: string;
}

/**
 * Néo dans les écrans de jeu, dans son médaillon. En 3D animée sur les grandes places : l'image
 * fixe reste affichée tant que le modèle charge, et si l'appareil ne peut pas l'afficher.
 */
export function NeoAvatar({ mood, still = false, className = '' }: Props) {
  const mascot = useRef<MascotHandle>(null);
  const { base, gesture } = MOODS[mood];

  useEffect(() => {
    if (!still && gesture) mascot.current?.perform(gesture);
  }, [still, gesture]);

  return (
    <span className={`neo-avatar ${className}`} data-mood={mood} data-live={!still} aria-hidden="true">
      <img className="neo-avatar__still" src={NEO_STILLS[mood]} alt="" draggable={false} />
      {!still && <Mascot ref={mascot} mood={base} framing="portrait" className="neo-avatar__live" />}
    </span>
  );
}
