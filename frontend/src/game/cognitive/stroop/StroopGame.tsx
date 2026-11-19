import { useEffect, useLayoutEffect, useRef, type CSSProperties } from 'react';
import type { PublicInstrument } from '../../types';
import { cogFr } from '../cognitive.fr';
import { pressProps, useDelay, useGameState, useKeys, usePause } from '../hooks';
import { stroopSequence, type StroopPair } from '../random';
import type { StroopSettings } from '../settings';
import { GameFrame, GameIntro, GameTop, GoScreen, NeoSays } from '../ui';

const t = cogFr.stroop;
const c = cogFr.common;

export interface StroopTrial {
  word: string;
  ink: string;
  response: string;
  rt_ms: number;
  practice?: true;
}

type Step = 'intro' | 'practice' | 'go' | 'run' | 'break' | 'done';
type Beat = 'fixation' | 'stimulus' | 'feedback';

interface State {
  step: Step;
  round: number;
  list: StroopPair[];
  index: number;
  beat: Beat;
  correct: boolean | null;
  streak: number;
  key: number;
}

const FEEDBACK_MS = 280;
const PRACTICE_RIGHT_MS = 1000;
const PRACTICE_WRONG_MS = 2400;
const MILESTONE = 5;

function ink(id: string): CSSProperties {
  return { '--ink': `var(--cog-ink-${id}, var(--color-text))` } as CSSProperties;
}

/** Tâche de Stroop : toucher la couleur de la peinture, pas celle que le mot raconte. */
export function StroopGame({
  instrument,
  settings,
  onFinish,
}: {
  instrument: PublicInstrument;
  settings: StroopSettings;
  onFinish: (trials: StroopTrial[]) => void;
}) {
  const ids = settings.colors.map((color) => color.id);
  const labels = Object.fromEntries(settings.colors.map((color) => [color.id, color.label]));
  const perRound = Math.ceil(settings.trials / settings.blocks);
  const [state, ref, commit] = useGameState<State>(() => ({
    step: 'intro',
    round: 0,
    list: [],
    index: 0,
    beat: 'fixation',
    correct: null,
    streak: 0,
    key: 0,
  }));
  const trials = useRef<StroopTrial[]>([]);
  const onset = useRef(0);
  const finished = useRef(false);
  const playing = state.step === 'practice' || state.step === 'run';
  const { paused, pause, resume } = usePause(playing);
  const pair = state.list[state.index];

  function roundSize(round: number) {
    return round < settings.blocks ? perRound : settings.trials - perRound * (settings.blocks - 1);
  }

  function startList(step: Step, round: number) {
    const current = ref.current;
    const count = step === 'practice' ? settings.practiceTrials : roundSize(round);
    commit({
      ...current,
      step,
      round,
      list: stroopSequence(ids, count, settings.congruentRatio),
      index: 0,
      beat: 'fixation',
      correct: null,
      key: current.key + 1,
    });
  }

  function respond(id: string) {
    const current = ref.current;
    if (current.beat !== 'stimulus' || paused || onset.current === 0) return;
    const shown = current.list[current.index];
    const correct = id === shown.ink;
    trials.current.push({
      word: shown.word,
      ink: shown.ink,
      response: id,
      rt_ms: Math.max(0, Math.round(performance.now() - onset.current)),
      ...(current.step === 'practice' ? { practice: true as const } : {}),
    });
    commit({ ...current, beat: 'feedback', correct, streak: correct ? current.streak + 1 : 0 });
  }

  function next() {
    const current = ref.current;
    if (current.beat !== 'feedback') return;
    if (current.index + 1 < current.list.length) {
      commit({ ...current, index: current.index + 1, beat: 'fixation', correct: null, key: current.key + 1 });
    } else if (current.step === 'practice') {
      commit({ ...current, step: 'go' });
    } else if (current.round < settings.blocks) {
      commit({ ...current, step: 'break' });
    } else {
      commit({ ...current, step: 'done' });
    }
  }

  function onResume() {
    resume();
    const current = ref.current;
    // Un mot affiché pendant la pause est remontré : l'essai n'a pas encore de réponse.
    if (current.beat !== 'feedback') commit({ ...current, beat: 'fixation', key: current.key + 1 });
  }

  useDelay(
    () => commit({ beat: 'stimulus' }),
    playing && state.beat === 'fixation' && !paused ? settings.fixationMs : null,
    state.key,
  );
  const feedbackDelay =
    state.step === 'practice' ? (state.correct ? PRACTICE_RIGHT_MS : PRACTICE_WRONG_MS) : FEEDBACK_MS;
  useDelay(next, playing && state.beat === 'feedback' && !paused ? feedbackDelay : null, state.key);

  // Le chrono part à l'image où le mot apparaît.
  useLayoutEffect(() => {
    onset.current = 0;
    if (!playing || state.beat !== 'stimulus' || paused) return;
    const frame = requestAnimationFrame(() => {
      onset.current = performance.now();
    });
    return () => cancelAnimationFrame(frame);
  }, [playing, state.beat, state.key, paused]);

  useKeys(
    (event) => {
      const color = settings.colors.find((entry) => entry.key === event.key.toLowerCase());
      if (!color) return;
      event.preventDefault();
      respond(color.id);
    },
    playing && !paused,
  );

  useEffect(() => {
    if (state.step === 'done' && !finished.current) {
      finished.current = true;
      onFinish(trials.current);
    }
  }, [state.step, onFinish]);

  if (state.step === 'intro') {
    const [shownInk, , shownWord] = settings.colors;
    const word = (shownWord ?? settings.colors[1]).label.toUpperCase();
    return (
      <GameIntro
        instrument={instrument}
        rules={t.rules}
        preview={
          <div className="cog-night cog-word-panel cog-word-panel--mini">
            <span className="cog-word" style={ink(shownInk.id)}>
              {word}
            </span>
          </div>
        }
        note={t.example(word, shownInk.label.toLowerCase(), shownInk.label)}
        keyboardNote={t.keyboardHint}
        onStart={() => (settings.practiceTrials > 0 ? startList('practice', 0) : startList('run', 1))}
      />
    );
  }
  if (state.step === 'go') {
    const practice = trials.current.filter((trial) => trial.practice);
    const right = practice.filter((trial) => trial.response === trial.ink).length;
    return (
      <GoScreen
        title={instrument.title}
        success={right * 2 >= practice.length}
        onGo={() => startList('run', 1)}
      />
    );
  }
  if (state.step === 'break' || state.step === 'done') {
    return (
      <section className="cog-intro cog-go">
        <GameTop title={instrument.title} />
        <NeoSays mood="cheer" big>
          {t.breakTitle(state.round)}
        </NeoSays>
        {state.step === 'break' && (
          <>
            <div className="cog-card">
              <p>{t.breakText}</p>
            </div>
            <button
              type="button"
              className="button button--primary cog-wide"
              onClick={() => startList('run', state.round + 1)}
              autoFocus
            >
              {t.nextRound(state.round + 1)}
            </button>
          </>
        )}
      </section>
    );
  }

  const practice = state.step === 'practice';
  const showing = state.beat === 'stimulus' || state.beat === 'feedback';
  const progress = practice
    ? `${c.practiceLabel} · ${t.progress(state.index + 1, state.list.length)}`
    : `${t.round(state.round, settings.blocks)} · ${t.progress(state.index + 1, state.list.length)}`;
  let message = t.focus;
  let mood: 'thinking' | 'cheer' | 'happy' = 'thinking';
  if (practice && state.beat === 'feedback') {
    message = state.correct ? t.practiceRight : t.practiceHint(t.inkFeminine[pair.ink] ?? labels[pair.ink]);
    mood = state.correct ? 'cheer' : 'happy';
  } else if (!practice && state.streak >= MILESTONE) {
    message = c.streak(state.streak - (state.streak % MILESTONE));
    mood = 'cheer';
  }

  return (
    <GameFrame
      title={instrument.title}
      progress={progress}
      mood={mood}
      message={message}
      paused={paused}
      onPause={pause}
      onResume={onResume}
    >
      <div className="cog-night cog-word-panel" data-beat={state.beat}>
        {showing && pair ? (
          <span className="cog-word" style={ink(pair.ink)} aria-hidden="true">
            {labels[pair.word].toUpperCase()}
          </span>
        ) : (
          <span className="cog-fixation" aria-hidden="true">
            +
          </span>
        )}
        {!practice && state.beat === 'feedback' && state.correct && (
          <span className="cog-tick" aria-hidden="true">
            ✓
          </span>
        )}
        <span className="visually-hidden" aria-live="polite">
          {state.beat === 'stimulus' && pair ? t.stimulus(labels[pair.word], labels[pair.ink].toLowerCase()) : ''}
        </span>
      </div>

      <div className="cog-colors" role="group" aria-label={t.colors}>
        {settings.colors.map((color) => (
          <button
            key={color.id}
            type="button"
            className="cog-color"
            style={ink(color.id)}
            aria-disabled={state.beat !== 'stimulus'}
            data-hint={
              practice && state.beat === 'feedback' && !state.correct && pair?.ink === color.id ? 'true' : undefined
            }
            {...pressProps(() => respond(color.id))}
          >
            <span className="cog-swatch" aria-hidden="true" />
            {color.label}
            <kbd className="cog-kbd" aria-hidden="true">
              {color.key.toUpperCase()}
            </kbd>
          </button>
        ))}
      </div>
    </GameFrame>
  );
}
