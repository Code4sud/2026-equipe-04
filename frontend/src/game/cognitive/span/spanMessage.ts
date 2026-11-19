import { cogFr } from '../cognitive.fr';
import type { SpanSettings } from '../settings';
import type { NeoMood } from '../ui';
import type { SpanState } from './useSpanGame';

const c = cogFr.common;

export interface SpanWords {
  watch: string;
  yourTurn: string;
  retry: (length: number) => string;
  practiceRetry: string;
  max: string;
  phaseEnd: string;
  end: string;
}

/** Ce que dit Néo pendant une partie d'empan : jamais de reproche, juste la suite. */
export function spanMessage(
  state: SpanState,
  settings: SpanSettings,
  words: SpanWords,
): { mood: NeoMood; text: string } {
  if (state.step === 'ready' || state.step === 'show') return { mood: 'thinking', text: words.watch };
  if (state.step === 'answer') return { mood: 'happy', text: words.yourTurn };
  if (state.step !== 'feedback') return { mood: 'happy', text: '' };
  if (state.practice) return { mood: 'happy', text: words.practiceRetry };

  const limits = settings.phases[state.phase];
  const last = state.phase === settings.phases.length - 1;
  if (state.correct) {
    if (state.length >= limits.max) return { mood: 'cheer', text: words.max };
    const cheer = c.cheers[state.key % c.cheers.length];
    return { mood: 'cheer', text: state.streak >= 2 ? `${cheer} ${c.streak(state.streak)}` : cheer };
  }
  if (state.failures < 2) return { mood: 'happy', text: words.retry(state.length) };
  return { mood: 'cheer', text: last ? words.end : words.phaseEnd };
}
