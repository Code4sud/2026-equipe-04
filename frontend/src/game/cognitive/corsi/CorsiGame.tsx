import { useState, type CSSProperties } from 'react';
import type { PublicInstrument } from '../../types';
import { cogFr } from '../cognitive.fr';
import { pressProps, useDelay } from '../hooks';
import type { SpanSettings } from '../settings';
import { spanMessage } from '../span/spanMessage';
import { useSpanGame, type SpanTrial } from '../span/useSpanGame';
import { useSpanNinja } from '../span/useSpanNinja';
import { GameFrame, GameIntro, GoScreen } from '../ui';

const t = cogFr.corsi;
const c = cogFr.common;

type Block = SpanSettings['blocks'][number];

function place(block: Block): CSSProperties {
  return { '--x': block.x, '--y': block.y } as CSSProperties;
}

function Preview({ blocks }: { blocks: Block[] }) {
  return (
    <div className="cog-night cog-board cog-board--mini">
      {blocks.map((block, index) => (
        <span
          key={block.id}
          className="cog-lantern"
          style={place(block)}
          data-lit={index === 4 ? 'true' : undefined}
        />
      ))}
    </div>
  );
}

/** Tâche des blocs de Corsi : des lanternes s'allument, le jeune les touche dans l'ordre. */
export function CorsiGame({
  instrument,
  settings,
  onFinish,
}: {
  instrument: PublicInstrument;
  settings: SpanSettings;
  onFinish: (trials: SpanTrial[]) => void;
}) {
  const game = useSpanGame(settings, onFinish, true);
  const { state } = game;
  const [flash, setFlash] = useState<{ id: number; at: number } | null>(null);
  useDelay(() => setFlash(null), flash ? 220 : null, flash?.at ?? 0);
  useSpanNinja(game, settings, (id) => tap(id), true);

  if (state.step === 'intro') {
    return (
      <GameIntro
        instrument={instrument}
        rules={t.rules}
        preview={<Preview blocks={settings.blocks} />}
        onStart={game.start}
      />
    );
  }
  if (state.step === 'go') {
    return <GoScreen title={instrument.title} success={state.correct === true} onGo={game.go} />;
  }

  const answering = state.step === 'answer';
  const lit = state.step === 'show' && state.shown >= 0 ? state.sequence[state.shown] : null;
  // Le reflet d'un appui ne doit jamais déborder sur la présentation suivante.
  const tapped = answering || state.step === 'feedback' ? flash?.id : null;
  const { mood, text } = spanMessage(state, settings, {
    watch: t.watch,
    yourTurn: t.yourTurn(state.sequence.length),
    retry: t.retry,
    practiceRetry: t.practiceRetry,
    max: t.max,
    phaseEnd: t.end,
    end: t.end,
  });

  function tap(id: number) {
    if (!answering || game.paused) return;
    setFlash({ id, at: performance.now() });
    game.press(id);
  }

  return (
    <GameFrame
      title={instrument.title}
      progress={state.practice ? c.practiceLabel : t.progress(state.length)}
      mood={mood}
      message={text}
      paused={game.paused}
      onPause={game.pause}
      onResume={game.resume}
    >
      <div
        className="cog-night cog-board"
        role="group"
        aria-label={t.board}
        data-answering={answering ? 'true' : undefined}
      >
        {settings.blocks.map((block) => (
          <button
            key={block.id}
            type="button"
            className="cog-lantern"
            style={place(block)}
            data-lit={lit === block.id || tapped === block.id ? 'true' : undefined}
            aria-label={t.lantern(block.id)}
            aria-disabled={!answering}
            {...pressProps(() => tap(block.id))}
          />
        ))}
      </div>
      <p className="cog-dots" aria-hidden="true">
        {state.sequence.map((_, index) => (
          <span key={index} data-done={index < state.response.length ? 'true' : undefined} />
        ))}
      </p>
      {state.step === 'feedback' && state.practice && (
        <button type="button" className="button button--primary cog-wide" onClick={game.advance} autoFocus>
          {c.retry}
        </button>
      )}
    </GameFrame>
  );
}
