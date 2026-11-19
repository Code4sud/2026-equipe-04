import { useEffect, useRef } from 'react';
import { useDelay, useGameState, usePause } from '../hooks';
import { spanSequence } from '../random';
import type { SpanSettings } from '../settings';

/**
 * Procédure d'empan partagée par les lanternes (Corsi) et le code secret (chiffres) :
 * entraînement, puis départ à la longueur minimale, +1 après une série exacte,
 * 2e essai à la même longueur après une erreur, arrêt après 2 erreurs ou à la longueur max.
 */

export type SpanStep = 'intro' | 'ready' | 'show' | 'answer' | 'feedback' | 'go' | 'done';

export interface SpanTrial {
  phase?: string;
  practice?: true;
  sequence: number[];
  response: number[];
  rt_ms: number;
}

export interface SpanState {
  phase: number;
  practice: boolean;
  practiceDone: number;
  length: number;
  failures: number;
  step: SpanStep;
  sequence: number[];
  /** Position de l'élément allumé pendant la présentation, -1 entre deux. */
  shown: number;
  response: number[];
  correct: boolean | null;
  streak: number;
  key: number;
}

const READY_MS = 900;
const FEEDBACK_MS = 1100;

export function useSpanGame(
  settings: SpanSettings,
  onFinish: (trials: SpanTrial[]) => void,
  autoSubmit: boolean,
) {
  const [state, ref, commit] = useGameState<SpanState>(() => ({
    phase: 0,
    practice: settings.practiceSpan > 0,
    practiceDone: 0,
    length: settings.phases[0].min,
    failures: 0,
    step: 'intro',
    sequence: [],
    shown: -1,
    response: [],
    correct: null,
    streak: 0,
    key: 0,
  }));
  const trials = useRef<SpanTrial[]>([]);
  const answerStart = useRef(0);
  const finished = useRef(false);
  const playing = state.step !== 'intro' && state.step !== 'go' && state.step !== 'done';
  const { paused, pause, resume } = usePause(playing);
  const phase = settings.phases[state.phase];

  function trialFrom(current: SpanState): SpanState {
    const length = current.practice ? settings.practiceSpan : current.length;
    return {
      ...current,
      step: 'ready',
      sequence: spanSequence(settings.symbols, length, settings.kind === 'digits'),
      shown: -1,
      response: [],
      correct: null,
      key: current.key + 1,
    };
  }

  function endPhase(current: SpanState) {
    const next = current.phase + 1;
    if (next >= settings.phases.length) {
      commit({ ...current, step: 'done' });
      return;
    }
    commit({
      ...current,
      phase: next,
      practice: settings.practiceSpan > 0,
      practiceDone: 0,
      length: settings.phases[next].min,
      failures: 0,
      streak: 0,
      step: 'intro',
    });
  }

  /** Après le retour d'un essai compté (ou le bouton « Réessayer » de l'entraînement). */
  function advance() {
    const current = ref.current;
    if (current.step !== 'feedback') return;
    if (current.practice) {
      commit(trialFrom(current));
      return;
    }
    const limits = settings.phases[current.phase];
    if (current.correct) {
      if (current.length >= limits.max) endPhase(current);
      else commit(trialFrom({ ...current, length: current.length + 1, failures: 0 }));
    } else if (current.failures >= 2) {
      endPhase(current);
    } else {
      commit(trialFrom(current));
    }
  }

  function submit(current: SpanState = ref.current) {
    if (current.step !== 'answer' || current.response.length !== current.sequence.length) return;
    const limits = settings.phases[current.phase];
    const expected = limits.backwards ? [...current.sequence].reverse() : current.sequence;
    const correct = expected.every((value, index) => current.response[index] === value);
    trials.current.push({
      ...(limits.id ? { phase: limits.id } : {}),
      ...(current.practice ? { practice: true as const } : {}),
      sequence: current.sequence,
      response: current.response,
      rt_ms: Math.max(0, Math.round(performance.now() - answerStart.current)),
    });
    if (current.practice) {
      const practiceDone = current.practiceDone + 1;
      const done = correct || practiceDone >= settings.practiceMax;
      commit({ ...current, practiceDone, correct, step: done ? 'go' : 'feedback' });
      return;
    }
    commit({
      ...current,
      correct,
      step: 'feedback',
      streak: correct ? current.streak + 1 : 0,
      failures: correct ? current.failures : current.failures + 1,
    });
  }

  function press(symbol: number) {
    const current = ref.current;
    if (current.step !== 'answer' || paused) return;
    if (current.response.length >= current.sequence.length) return;
    const response = [...current.response, symbol];
    if (autoSubmit && response.length === current.sequence.length) submit({ ...current, response });
    else commit({ response });
  }

  function erase() {
    const current = ref.current;
    if (current.step === 'answer' && !paused && current.response.length) {
      commit({ response: current.response.slice(0, -1) });
    }
  }

  function start() {
    commit(trialFrom(ref.current));
  }

  function go() {
    const current = ref.current;
    const length = settings.phases[current.phase].min;
    commit(trialFrom({ ...current, practice: false, length, failures: 0, streak: 0 }));
  }

  function onResume() {
    const lost = resume();
    const current = ref.current;
    // Une présentation coupée est rejouée avec une nouvelle série : rien n'est compté.
    if (current.step === 'ready' || current.step === 'show') commit(trialFrom(current));
    else if (current.step === 'answer') answerStart.current += lost;
  }

  useDelay(
    () => commit({ step: 'show' }),
    state.step === 'ready' && !paused ? READY_MS : null,
    state.key,
  );
  useDelay(
    advance,
    state.step === 'feedback' && !state.practice && !paused ? FEEDBACK_MS : null,
    state.key,
  );

  // Présentation : un élément allumé à la fois, puis la main passe au jeune.
  useEffect(() => {
    if (paused || state.step !== 'show') return;
    const period = settings.itemMs + settings.gapMs;
    const handles: number[] = [];
    state.sequence.forEach((_, index) => {
      handles.push(window.setTimeout(() => commit({ shown: index }), index * period));
      handles.push(window.setTimeout(() => commit({ shown: -1 }), index * period + settings.itemMs));
    });
    handles.push(
      window.setTimeout(() => {
        answerStart.current = performance.now();
        commit({ step: 'answer', shown: -1 });
      }, state.sequence.length * period),
    );
    return () => handles.forEach((handle) => window.clearTimeout(handle));
  }, [paused, state.step, state.key, state.sequence, settings.itemMs, settings.gapMs, commit]);

  useEffect(() => {
    if (state.step === 'done' && !finished.current) {
      finished.current = true;
      onFinish(trials.current);
    }
  }, [state.step, onFinish]);

  return {
    state,
    phase,
    paused,
    pause,
    resume: onResume,
    start,
    go,
    press,
    erase,
    submit: () => submit(),
    advance,
  };
}
