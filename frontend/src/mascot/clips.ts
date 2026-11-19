/**
 * Moments de Néo et animations associées.
 *
 * Chaque moment liste des noms de clips par ordre de préférence : le premier présent dans
 * le modèle est joué. Une nouvelle animation s'ajoute ici, sans toucher au reste du code.
 * `talk` alterne entre tous ses clips disponibles.
 */
export type ClipPlayback = 'loop' | 'once' | 'hold';

interface MoodDefinition {
  clips: string[];
  playback: ClipPlayback;
  rotate?: boolean;
}

export const MOODS = {
  idle: { clips: ['repos', 'ecoute'], playback: 'loop' },
  listen: { clips: ['ecoute', 'repos'], playback: 'loop' },
  think: { clips: ['reflexion', 'reflechit', 'repos'], playback: 'loop' },
  talk: { clips: ['parle_1', 'parle_2', 'parle_3', 'parle'], playback: 'loop', rotate: true },
  calm: { clips: ['calme', 'repos'], playback: 'loop' },
  greet: { clips: ['salut', 'bras_ouverts'], playback: 'once' },
  openArms: { clips: ['bras_ouverts', 'salut'], playback: 'once' },
  shrug: { clips: ['pas_grave'], playback: 'once' },
  impressed: { clips: ['pas_mal', 'encourage'], playback: 'once' },
  reveal: { clips: ['detection', 'pas_mal'], playback: 'once' },
  cardOut: { clips: ['carte_sortir'], playback: 'hold' },
  cardKeep: { clips: ['carte_garder'], playback: 'once' },
  cardDrop: { clips: ['carte_poser'], playback: 'once' },
  cheer: { clips: ['encourage', 'pas_mal'], playback: 'once' },
  laugh: { clips: ['rigole'], playback: 'once' },
} satisfies Record<string, MoodDefinition>;

export type MoodName = keyof typeof MOODS;

/** Ces états répondent à une action du jeune : ils coupent le geste en cours. */
export const INTERRUPTING_MOODS: ReadonlySet<MoodName> = new Set<MoodName>(['think', 'calm']);

/** Choisit le clip d'un moment, avec repli si le modèle ne le contient pas. */
export function chooseClip(mood: MoodName, available: string[], turn: number): string | null {
  const definition: MoodDefinition = MOODS[mood];
  const candidates = definition.clips.filter((clip) => available.includes(clip));
  if (candidates.length) {
    return definition.rotate ? candidates[turn % candidates.length] : candidates[0];
  }
  if (definition.playback !== 'loop') return null;
  return available.includes('repos') ? 'repos' : (available[0] ?? null);
}
