import type { PublicInstrument } from '../../types';
import { cogFr } from '../cognitive.fr';
import { pressProps, useKeys } from '../hooks';
import type { SpanSettings } from '../settings';
import { spanMessage } from '../span/spanMessage';
import { useSpanGame, type SpanTrial } from '../span/useSpanGame';
import { useSpanNinja } from '../span/useSpanNinja';
import { GameFrame, GameIntro, GameTop, GoScreen, NeoSays } from '../ui';

const t = cogFr.digits;
const c = cogFr.common;

function Preview() {
  return (
    <div className="cog-night cog-display cog-display--mini">
      <span>4</span>
      <span className="cog-display__ghost">7</span>
      <span className="cog-display__ghost">2</span>
    </div>
  );
}

function BackwardIntro({ title, onStart }: { title: string; onStart: () => void }) {
  return (
    <section className="cog-intro">
      <GameTop title={title} />
      <NeoSays mood="cheer" big>
        {t.backwardText}
      </NeoSays>
      <div className="cog-card cog-how">
        <h2>{t.backwardTitle}</h2>
        <div className="cog-preview" aria-hidden="true">
          <div className="cog-night cog-display cog-display--mini">
            <span>3</span>
            <span>8</span>
            <span>1</span>
            <span className="cog-display__arrow">→</span>
            <span>1</span>
            <span>8</span>
            <span>3</span>
          </div>
        </div>
        <p>{t.backwardExample}</p>
      </div>
      <button type="button" className="button button--primary cog-wide" onClick={onStart} autoFocus>
        {c.practice}
      </button>
    </section>
  );
}

/** Empan de chiffres : à l'endroit, puis à l'envers. */
export function DigitsGame({
  instrument,
  settings,
  onFinish,
}: {
  instrument: PublicInstrument;
  settings: SpanSettings;
  onFinish: (trials: SpanTrial[]) => void;
}) {
  const game = useSpanGame(settings, onFinish, false);
  useSpanNinja(game, settings, game.press, false);
  const { state, phase } = game;
  const answering = state.step === 'answer';
  const complete = answering && state.response.length === state.sequence.length;

  useKeys((event) => {
    if (!answering) return;
    if ((event.key === 'Enter' || event.key === ' ') && (event.target as HTMLElement).closest('button')) return;
    if (/^[0-9]$/.test(event.key) && settings.symbols.includes(Number(event.key))) {
      event.preventDefault();
      game.press(Number(event.key));
    } else if (event.key === 'Backspace') {
      event.preventDefault();
      game.erase();
    } else if (event.key === 'Enter') {
      event.preventDefault();
      game.submit();
    }
  }, !game.paused);

  if (state.step === 'intro') {
    return state.phase === 0 ? (
      <GameIntro
        instrument={instrument}
        rules={t.rules}
        preview={<Preview />}
        keyboardNote={t.keyboardHint}
        onStart={game.start}
      />
    ) : (
      <BackwardIntro title={instrument.title} onStart={game.start} />
    );
  }
  if (state.step === 'go') {
    return <GoScreen title={instrument.title} success={state.correct === true} onGo={game.go} />;
  }

  const shown = state.step === 'show' && state.shown >= 0 ? state.sequence[state.shown] : null;
  const typing = answering || state.step === 'feedback';
  const { mood, text } = spanMessage(state, settings, {
    watch: t.watch,
    yourTurn: t.yourTurn(state.sequence.length, phase.backwards),
    retry: t.retry,
    practiceRetry: t.practiceRetry(phase.backwards ? [...state.sequence].reverse() : state.sequence),
    max: t.max,
    phaseEnd: t.phaseEnd,
    end: t.end,
  });
  const length = state.practice ? state.sequence.length : state.length;

  return (
    <GameFrame
      title={instrument.title}
      progress={state.practice ? `${c.practiceLabel} · ${t.length(length)}` : t.progress(length, phase.backwards)}
      mood={mood}
      message={text}
      paused={game.paused}
      onPause={game.pause}
      onResume={game.resume}
    >
      <div className="cog-night cog-display" data-feedback={state.step === 'feedback' ? String(state.correct) : undefined}>
        {typing ? (
          <span className="cog-slots" aria-hidden="true">
            {state.sequence.map((_, index) => (
              <span key={index} className="cog-slot" data-filled={index < state.response.length ? 'true' : undefined}>
                {state.response[index] ?? ''}
              </span>
            ))}
          </span>
        ) : (
          <span className="cog-display__digit" aria-hidden="true" key={`${state.key}-${state.shown}`}>
            {shown ?? ''}
          </span>
        )}
        <span className="visually-hidden" aria-live="polite">
          {typing ? t.typed(state.response, state.sequence.length) : (shown ?? '')}
        </span>
      </div>

      <div className="cog-keypad" role="group" aria-label={t.keypad} data-active={answering ? 'true' : undefined}>
        {settings.symbols.map((digit) => (
          <button
            key={digit}
            type="button"
            className="cog-key"
            aria-disabled={!answering}
            {...pressProps(() => game.press(digit))}
          >
            {digit}
          </button>
        ))}
        <button
          type="button"
          className="cog-key cog-key--small"
          aria-disabled={!answering || state.response.length === 0}
          {...pressProps(game.erase)}
        >
          {t.erase}
        </button>
        <button
          type="button"
          className="cog-key cog-key--go"
          aria-disabled={!complete}
          onClick={game.submit}
        >
          {t.validate}
        </button>
      </div>

      {state.step === 'feedback' && state.practice && (
        <button type="button" className="button button--primary cog-wide" onClick={game.advance} autoFocus>
          {c.retry}
        </button>
      )}
    </GameFrame>
  );
}
