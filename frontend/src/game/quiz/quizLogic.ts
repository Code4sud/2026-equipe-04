import type { GameItem, StoredAnswer, YouthTrait } from '../types';

export const QUIZ_ID = 'onboarding';
/** Même règle que le serveur (service.XP_PER_ANSWER) : sert à afficher l'XP déjà gagnée à la reprise. */
export const XP_PER_ANSWER = 2;
export const HIGHLIGHT_COUNT = 3;
/** Questions posées d'affilée avant de proposer de continuer ou de revenir plus tard. */
export const SERIES_SIZE = 10;

/**
 * Questions vues pendant la séance (répondues ou passées depuis l'ouverture du quiz), dans l'ordre
 * où elles ont été posées : celui de la partie, puisqu'on avance toujours vers la première question
 * jamais vue.
 */
export function sittingOrder(
  items: GameItem[],
  answers: Record<string, StoredAnswer>,
  seenBefore: ReadonlySet<string>,
): string[] {
  return items.filter((item) => answers[item.id] && !seenBefore.has(item.id)).map((item) => item.id);
}

export interface SeriesSpot {
  /** Questions déjà vues dans la série montrée : toutes pour une série terminée. */
  done: number;
  /**
   * Place de la question affichée dans cette série (0 pour la première). Null pour une question
   * vue lors d'une séance précédente : on montre alors la série en cours, sans repère.
   */
  position: number | null;
}

/**
 * Où en est la série sur l'écran d'une question. `series` : numéro de la série en cours dans la
 * séance (0 pour la première). Une question jamais vue est la prochaine de la série en cours ; une
 * question revue avec « Retour » montre la série d'où elle vient.
 */
export function seriesSpot(sitting: string[], series: number, itemId: string, seen: boolean): SeriesSpot {
  const order = seen ? sitting.indexOf(itemId) : sitting.length;
  const current = Math.min(SERIES_SIZE, sitting.length - series * SERIES_SIZE);
  if (order === -1) return { done: current, position: null };
  const finished = Math.floor(order / SERIES_SIZE) < series;
  return { done: finished ? SERIES_SIZE : current, position: order % SERIES_SIZE };
}

/** Durée d'une série, d'après la durée annoncée pour tout le quiz. */
export function seriesMinutes(totalMinutes: number, itemCount: number) {
  return Math.max(1, Math.round((totalMinutes * Math.min(SERIES_SIZE, itemCount)) / Math.max(1, itemCount)));
}

/** Force d'un trait, comme le serveur pour les temps forts : écart au milieu, ou au-dessus du milieu. */
function strength(trait: YouthTrait) {
  if (trait.value === null) return 0;
  return trait.kind === 'bipolar' ? Math.abs(trait.value - 50) : trait.value - 50;
}

/** Les traits les plus marqués de la fiche, pour résumer un quiz déjà terminé. */
export function strongestTraits(traits: YouthTrait[], limit = HIGHLIGHT_COUNT) {
  return traits
    .filter((trait) => strength(trait) > 0)
    .sort((a, b) => strength(b) - strength(a))
    .slice(0, limit);
}

const BADGE_EMOJI: Record<string, string> = {
  paw: '🐾',
  dice: '🎲',
  map: '🗺️',
  star: '⭐',
  stars: '✨',
  flag: '🚩',
};

export function badgeEmoji(icon: string) {
  return BADGE_EMOJI[icon] ?? '🏅';
}
