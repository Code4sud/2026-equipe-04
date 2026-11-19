import type { Chapter, GameItem, PublicInstrument, StoredAnswer, YouthTrait } from '../types';

export const QUIZ_ID = 'onboarding';
/** Même règle que le serveur (service.XP_PER_ANSWER) : sert à afficher l'XP déjà gagnée à la reprise. */
export const XP_PER_ANSWER = 2;
export const HIGHLIGHT_COUNT = 3;

type Answers = Record<string, StoredAnswer>;

/** Une question reste à faire si elle n'a jamais été vue ou si elle a été passée. */
export function isPending(item: GameItem, answers: Answers) {
  const stored = answers[item.id];
  return !stored || stored.skipped;
}

/** Prochaine question à faire après `from`, en ignorant `exclude` ; `items.length` s'il n'y en a plus. */
export function nextPendingIndex(items: GameItem[], answers: Answers, from: number, exclude?: string) {
  const found = items.findIndex(
    (item, position) => position > from && item.id !== exclude && isPending(item, answers),
  );
  return found === -1 ? items.length : found;
}

export interface ChapterInfo {
  chapter: Chapter;
  position: number;
  total: number;
}

export function chapterOf(instrument: PublicInstrument, item: GameItem | null): ChapterInfo | null {
  const chapters = instrument.chapters ?? [];
  const position = chapters.findIndex((chapter) => chapter.id === item?.chapter);
  if (position === -1) return null;
  return { chapter: chapters[position], position: position + 1, total: chapters.length };
}

/** Avancement de chaque chapitre, de 0 à 1, d'après la question affichée. */
export function chapterProgress(instrument: PublicInstrument, index: number) {
  const items = instrument.items ?? [];
  return (instrument.chapters ?? []).map((chapter) => {
    const positions = items.flatMap((item, position) => (item.chapter === chapter.id ? [position] : []));
    const done = positions.filter((position) => position < index).length;
    return { id: chapter.id, title: chapter.title, ratio: positions.length ? done / positions.length : 0 };
  });
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
