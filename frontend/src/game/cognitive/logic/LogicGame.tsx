import { useEffect, useRef } from 'react';
import type { PublicInstrument } from '../../types';
import { cogFr } from '../cognitive.fr';
import { useDelay, useGameState, useKeys, usePause } from '../hooks';
import type { LogicPuzzle, LogicSettings } from '../settings';
import { pickOne, useNinja, useNinjaStep } from '../../ninja';
import { GameFrame, GameIntro, GoScreen, type NeoMood } from '../ui';
import { LogicFigure, describeCell } from './LogicFigure';

const t = cogFr.logic;
const c = cogFr.common;
const LETTERS = 'ABCDEF';

export interface LogicTrial {
  puzzle: string;
  response: string | null;
  rt_ms: number;
  practice?: true;
}

type Step = 'intro' | 'practice' | 'go' | 'run' | 'done';
type Feedback = 'right' | 'wrong' | 'noted' | 'skipped' | null;

interface State {
  step: Step;
  index: number;
  selected: string | null;
  feedback: Feedback;
  key: number;
}

const NEXT_MS = 700;

function optionText(puzzle: LogicPuzzle, optionId: string): string {
  const option = puzzle.options.find((entry) => entry.id === optionId);
  if (!option) return '';
  return option.label ?? describeCell(option.cell ?? null);
}

function Stimulus({ puzzle }: { puzzle: LogicPuzzle }) {
  if (puzzle.kind === 'series') {
    return (
      <p className="cog-series" aria-label={`${(puzzle.sequence ?? []).join(', ')}, ?`}>
        {(puzzle.sequence ?? []).map((value, index) => (
          <span key={index} className="cog-chip" aria-hidden="true">
            {value}
          </span>
        ))}
        <span className="cog-chip cog-chip--ask" aria-hidden="true">
          ?
        </span>
      </p>
    );
  }
  const grid = puzzle.grid ?? [];
  return (
    <div className="cog-matrix" role="img" aria-label={t.grid(grid.map(describeCell))}>
      {grid.map((cell, index) =>
        cell ? (
          <span key={index} className="cog-cell">
            <LogicFigure cell={cell} />
          </span>
        ) : (
          <span key={index} className="cog-cell cog-cell--ask" aria-hidden="true">
            ?
          </span>
        ),
      )}
    </div>
  );
}

/** Énigmes originales (suites, matrices). La correction est faite par le serveur, à la fin. */
export function LogicGame({
  instrument,
  settings,
  onFinish,
}: {
  instrument: PublicInstrument;
  settings: LogicSettings;
  onFinish: (trials: LogicTrial[]) => void;
}) {
  const [state, ref, commit] = useGameState<State>(() => ({
    step: 'intro',
    index: 0,
    selected: null,
    feedback: null,
    key: 0,
  }));
  const trials = useRef<LogicTrial[]>([]);
  const shownAt = useRef(0);
  const finished = useRef(false);
  const playing = state.step === 'practice' || state.step === 'run';
  const { paused, pause, resume } = usePause(playing);
  const list = state.step === 'practice' ? settings.practice : settings.puzzles;
  const puzzle = list[state.index];

  useEffect(() => {
    shownAt.current = performance.now();
  }, [state.key]);

  function begin(step: Step) {
    const current = ref.current;
    commit({ ...current, step, index: 0, selected: null, feedback: null, key: current.key + 1 });
  }

  function record(response: string | null) {
    const current = ref.current;
    if (!playing || paused || current.feedback) return;
    const practice = current.step === 'practice';
    const shown = (practice ? settings.practice : settings.puzzles)[current.index];
    trials.current.push({
      puzzle: shown.id,
      response,
      rt_ms: Math.max(0, Math.round(performance.now() - shownAt.current)),
      ...(practice ? { practice: true as const } : {}),
    });
    let feedback: Feedback = response === null ? 'skipped' : 'noted';
    if (practice) feedback = response !== null && response === shown.answer ? 'right' : 'wrong';
    commit({ ...current, selected: response, feedback });
  }

  function next() {
    const current = ref.current;
    if (!current.feedback) return;
    const size = (current.step === 'practice' ? settings.practice : settings.puzzles).length;
    if (current.index + 1 < size) {
      commit({ ...current, index: current.index + 1, selected: null, feedback: null, key: current.key + 1 });
    } else {
      commit({ ...current, step: current.step === 'practice' ? 'go' : 'done', feedback: null });
    }
  }

  function select(optionId: string) {
    const current = ref.current;
    if (playing && !paused && !current.feedback) commit({ ...current, selected: optionId });
  }

  function onResume() {
    shownAt.current += resume();
  }

  useDelay(
    next,
    state.step === 'run' && state.feedback && !paused ? NEXT_MS : null,
    state.key,
  );

  useKeys(
    (event) => {
      if (!puzzle || state.feedback) return;
      if ((event.key === 'Enter' || event.key === ' ') && (event.target as HTMLElement).closest('button')) return;
      const letter = event.key.toUpperCase();
      const position = LETTERS.indexOf(letter) >= 0 ? LETTERS.indexOf(letter) : Number(event.key) - 1;
      if (event.key.length === 1 && position >= 0 && position < puzzle.options.length) {
        event.preventDefault();
        select(puzzle.options[position].id);
      } else if (event.key === 'Enter' && state.selected) {
        event.preventDefault();
        record(state.selected);
      }
    },
    playing && !paused,
  );

  // Mode ninja (démo) : lit l'énigme, choisit une réponse, la valide. Les réponses des énigmes
  // comptées ne sont jamais dans l'app : hors entraînement, il choisit au hasard.
  const ninja = useNinja();
  let ninjaAction: (() => void) | null = null;
  let ninjaDelay = 1400;
  if (ninja && !paused) {
    if (state.step === 'intro') {
      ninjaAction = () => begin(settings.practice.length ? 'practice' : 'run');
    } else if (state.step === 'go') {
      ninjaAction = () => begin('run');
    } else if (playing && puzzle) {
      if (state.feedback) {
        // Pendant l'entraînement, « Suivant » attend un appui ; ensuite le jeu avance seul.
        if (state.step === 'practice') ninjaAction = next;
        ninjaDelay = 1300;
      } else if (!state.selected) {
        const choice = puzzle.answer ?? pickOne(puzzle.options).id;
        ninjaAction = () => select(choice);
        ninjaDelay = 1600;
      } else {
        const chosen = state.selected;
        ninjaAction = () => record(chosen);
        ninjaDelay = 700;
      }
    }
  }
  useNinjaStep(ninja, ninjaAction, ninjaDelay);

  useEffect(() => {
    if (state.step === 'done' && !finished.current) {
      finished.current = true;
      onFinish(trials.current);
    }
  }, [state.step, onFinish]);

  if (state.step === 'intro') {
    return (
      <GameIntro
        instrument={instrument}
        rules={t.rules}
        preview={
          <p className="cog-series cog-series--mini">
            <span className="cog-chip">2</span>
            <span className="cog-chip">4</span>
            <span className="cog-chip">6</span>
            <span className="cog-chip cog-chip--ask">?</span>
          </p>
        }
        note={t.secret}
        onStart={() => begin(settings.practice.length ? 'practice' : 'run')}
      />
    );
  }
  if (state.step === 'go') {
    const practice = trials.current.filter((trial) => trial.practice);
    const right = practice.filter(
      (trial) => trial.response === settings.practice.find((entry) => entry.id === trial.puzzle)?.answer,
    ).length;
    return <GoScreen title={instrument.title} success={right * 2 >= practice.length} onGo={() => begin('run')} />;
  }
  if (!puzzle) return null;

  const practice = state.step === 'practice';
  let mood: NeoMood = 'thinking';
  let message = puzzle.kind === 'matrix' ? t.tipMatrix : t.tipSeries;
  if (state.feedback === 'right') {
    mood = 'cheer';
    message = `${t.practiceRight} ${puzzle.hint ?? ''}`.trim();
  } else if (state.feedback === 'wrong') {
    mood = 'happy';
    message = `${t.practiceWrong} ${puzzle.hint ?? ''}`.trim();
  } else if (state.feedback === 'noted') {
    mood = 'cheer';
    message = t.noted[state.key % t.noted.length];
  } else if (state.feedback === 'skipped') {
    mood = 'happy';
    message = t.skipped;
  }
  const progress = practice
    ? `${c.practiceLabel} · ${t.progress(state.index + 1, list.length)}`
    : t.progress(state.index + 1, list.length);
  const reveal = practice && state.feedback !== null;

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
      {!practice && (
        <div className="game-progress" aria-hidden="true">
          <span style={{ width: `${(state.index / list.length) * 100}%` }} />
        </div>
      )}
      <section className="cog-card cog-puzzle" aria-label={puzzle.prompt}>
        <h2 className="cog-puzzle__prompt">{puzzle.prompt}</h2>
        <Stimulus puzzle={puzzle} />
      </section>
      <div
        className={`cog-options cog-options--${puzzle.kind}`}
        role="group"
        aria-label={t.choices}
      >
        {puzzle.options.map((option, index) => {
          const letter = LETTERS[index] ?? String(index + 1);
          return (
            <button
              key={option.id}
              type="button"
              className="cog-option"
              aria-pressed={state.selected === option.id}
              aria-disabled={state.feedback !== null}
              aria-label={t.choice(letter, optionText(puzzle, option.id))}
              data-answer={reveal && option.id === puzzle.answer ? 'true' : undefined}
              onClick={() => select(option.id)}
            >
              <span className="cog-option__letter" aria-hidden="true">
                {letter}
              </span>
              {option.cell ? (
                <LogicFigure cell={option.cell} />
              ) : (
                <span className="cog-option__label" aria-hidden="true">
                  {option.label}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <div className="cog-actions">
        {reveal ? (
          <button type="button" className="button button--primary cog-wide" onClick={next} autoFocus>
            {c.next}
          </button>
        ) : (
          <>
            <button
              type="button"
              className="button button--primary cog-wide"
              aria-disabled={!state.selected || state.feedback !== null}
              onClick={() => state.selected && record(state.selected)}
            >
              {t.validate}
            </button>
            <button
              type="button"
              className="link-button"
              aria-disabled={state.feedback !== null}
              onClick={() => record(null)}
            >
              {t.skip}
            </button>
          </>
        )}
      </div>
    </GameFrame>
  );
}
