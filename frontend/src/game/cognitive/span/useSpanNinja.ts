import { useRef } from 'react';
import { useNinja, useNinjaStep } from '../../ninja';
import type { SpanSettings } from '../settings';
import type { useSpanGame } from './useSpanGame';

/**
 * Mode ninja des empans (lanternes, code secret) : regarde la série, puis la retape touche par
 * touche. Il réussit souvent et se trompe de plus en plus quand la série s'allonge, comme un vrai
 * joueur : la partie s'arrête d'elle-même après deux erreurs, ou à la longueur maximale.
 */
export function useSpanNinja(
  game: ReturnType<typeof useSpanGame>,
  settings: SpanSettings,
  tap: (symbol: number) => void,
  autoSubmit: boolean,
) {
  const active = useNinja();
  const { state } = game;
  const plan = useRef<{ key: number; response: number[] } | null>(null);
  let action: (() => void) | null = null;
  let delay = 600;

  if (active && !game.paused) {
    if (state.step === 'intro') {
      action = game.start;
      delay = 1400;
    } else if (state.step === 'go') {
      action = game.go;
      delay = 1400;
    } else if (state.step === 'feedback' && state.practice) {
      action = game.advance;
      delay = 900;
    } else if (state.step === 'answer') {
      if (plan.current?.key !== state.key) {
        const limits = settings.phases[state.phase];
        const expected = limits.backwards ? [...state.sequence].reverse() : [...state.sequence];
        const success = state.practice || Math.random() < Math.max(0.15, 1.25 - state.sequence.length * 0.17);
        if (!success && expected.length >= 2) {
          const at = Math.floor(Math.random() * (expected.length - 1));
          [expected[at], expected[at + 1]] = [expected[at + 1], expected[at]];
          if (expected[at] === expected[at + 1]) {
            const other = settings.symbols.find((symbol) => symbol !== expected[at]);
            if (other !== undefined) expected[at] = other;
          }
        }
        plan.current = { key: state.key, response: expected };
      }
      const response = plan.current.response;
      if (state.response.length < response.length) {
        const symbol = response[state.response.length];
        action = () => tap(symbol);
        delay = state.response.length === 0 ? 600 : 350;
      } else if (!autoSubmit) {
        action = game.submit;
        delay = 600;
      }
    }
  }
  useNinjaStep(active, action, delay);
}
