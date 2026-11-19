import { cogFr } from './cognitive.fr';
import type { GameSettings } from './settings';

export interface Stat {
  label: string;
  value: string;
  unit?: string;
}

export interface GameSummary {
  /** Seulement des réussites : une valeur nulle n'est jamais affichée. */
  stats: Stat[];
  /** Score gardé comme record perso sur cet appareil, null si rien à retenir. */
  score: number | null;
  empty: string;
}

type Metrics = Record<string, unknown> | null;

function count(metrics: Metrics, ...path: string[]): number {
  let value: unknown = metrics;
  for (const key of path) {
    value = value && typeof value === 'object' ? (value as Record<string, unknown>)[key] : undefined;
  }
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

/** Ce que le jeune voit à la fin : ses meilleurs moments, jamais un pourcentage. */
export function summarize(settings: GameSettings, metrics: Metrics): GameSummary {
  switch (settings.kind) {
    case 'corsi': {
      const t = cogFr.corsi.stats;
      const span = count(metrics, 'span');
      const series = count(metrics, 'correct');
      return {
        stats: span
          ? [
              { label: t.record, value: String(span), unit: t.recordUnit(span) },
              { label: t.series, value: String(series) },
            ]
          : [],
        score: span || null,
        empty: cogFr.corsi.empty,
      };
    }
    case 'digits': {
      const t = cogFr.digits.stats;
      const forward = count(metrics, 'phases', 'forward', 'span');
      const backward = count(metrics, 'phases', 'backward', 'span');
      const single = forward || backward ? 0 : count(metrics, 'span');
      const stats: Stat[] = [];
      if (forward || single) {
        stats.push({ label: t.forward, value: String(forward || single), unit: t.unit(forward || single) });
      }
      if (backward) stats.push({ label: t.backward, value: String(backward), unit: t.unit(backward) });
      return { stats, score: forward + backward + single || null, empty: cogFr.digits.empty };
    }
    case 'stroop': {
      const t = cogFr.stroop.stats;
      const streak = count(metrics, 'best_streak');
      const fastest = count(metrics, 'fastest_rt_ms');
      const stats: Stat[] = [];
      if (streak) stats.push({ label: t.streak, value: String(streak), unit: t.streakUnit });
      if (fastest) stats.push({ label: t.fastest, value: t.fastestValue(fastest), unit: t.fastestUnit });
      return { stats, score: streak || null, empty: cogFr.stroop.empty };
    }
    case 'logic': {
      const t = cogFr.logic.stats;
      const solved = count(metrics, 'solved');
      const streak = count(metrics, 'best_streak');
      const stats: Stat[] = [];
      if (solved) stats.push({ label: t.solved, value: String(solved), unit: t.solvedUnit(solved) });
      if (streak >= 2) stats.push({ label: t.streak, value: String(streak), unit: t.streakUnit });
      return { stats, score: solved || null, empty: cogFr.logic.empty };
    }
  }
}

const RECORDS_KEY = 'potentiel.cognitive.records';

type Records = Record<string, Record<string, number>>;

/**
 * Record perso, gardé sur cet appareil seulement (confort, pas une donnée de suivi).
 * Renvoie « new » s'il est battu, « first » pour un premier record, null sinon.
 */
export function keepRecord(userId: string, instrumentId: string, score: number | null): 'new' | 'first' | null {
  if (score === null) return null;
  try {
    const all = JSON.parse(localStorage.getItem(RECORDS_KEY) ?? '{}') as Records;
    const mine = all[userId] ?? {};
    const previous = mine[instrumentId];
    if (typeof previous === 'number' && previous >= score) return null;
    all[userId] = { ...mine, [instrumentId]: score };
    localStorage.setItem(RECORDS_KEY, JSON.stringify(all));
    return typeof previous === 'number' ? 'new' : 'first';
  } catch {
    return null;
  }
}
