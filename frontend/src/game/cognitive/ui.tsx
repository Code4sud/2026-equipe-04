import { useEffect, useRef, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { NeoAvatar, type NeoMood } from '../neo/NeoAvatar';
import type { PublicInstrument } from '../types';
import { cogFr } from './cognitive.fr';
import { NinjaContextButton } from '../ninja';
import { useKeys } from './hooks';

const t = cogFr.common;
export const GAMES_PATH = '/jeune/jeux';

/** Évite qu'un « : », « ! » ou « ? » se retrouve seul en début de ligne. */
export function frenchSpacing(text: string): string {
  return text.replace(/ ([:;!?])/g, '\u00a0$1');
}

export type { NeoMood };

/**
 * Néo dans les jeux chronométrés. En image fixe par défaut : pendant les essais, une animation
 * 3D distrairait et prendrait du temps de calcul au moment où l'on mesure les réactions.
 */
export function NeoSlot({ mood, still = true }: { mood: NeoMood; still?: boolean }) {
  return <NeoAvatar mood={mood} still={still} className="neo-slot" />;
}

/**
 * Néo et sa bulle. La bulle reste montée d'un essai à l'autre pour être annoncée.
 * En grand (présentation, « Prêt ? », bilan), Néo est en 3D ; en petit, pendant les essais, fixe.
 */
export function NeoSays({
  mood,
  children,
  big = false,
  live = true,
}: {
  mood: NeoMood;
  children: ReactNode;
  big?: boolean;
  live?: boolean;
}) {
  return (
    <div className={big ? 'cog-neo cog-neo--big' : 'cog-neo'}>
      <NeoSlot mood={mood} still={!big} />
      <p className="cog-says" aria-live={live ? 'polite' : undefined}>
        {typeof children === 'string' ? frenchSpacing(children) : children}
      </p>
    </div>
  );
}

function PauseIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <rect x="5" y="4" width="3.2" height="12" rx="1.2" fill="currentColor" />
      <rect x="11.8" y="4" width="3.2" height="12" rx="1.2" fill="currentColor" />
    </svg>
  );
}

function BackIcon() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <path
        d="M12.5 4.5L7 10l5.5 5.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function GameTop({
  title,
  progress,
  onPause,
}: {
  title: string;
  progress?: string;
  onPause?: () => void;
}) {
  return (
    <header className="cog-top">
      {onPause ? (
        <button type="button" className="cog-round" onClick={onPause} aria-label={t.pause} title={t.pause}>
          <PauseIcon />
        </button>
      ) : (
        <Link className="cog-round" to={GAMES_PATH} aria-label={t.back} title={t.back}>
          <BackIcon />
        </Link>
      )}
      <div className="cog-top__text">
        <h1>{title}</h1>
        {progress && <p className="cog-top__progress">{progress}</p>}
      </div>
      <NinjaContextButton />
    </header>
  );
}

export function PauseOverlay({ onResume }: { onResume: () => void }) {
  const resume = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    resume.current?.focus();
  }, []);
  useKeys((event) => {
    if (event.key === 'Escape') onResume();
  });
  return (
    <div className="cog-overlay" role="dialog" aria-modal="true" aria-labelledby="cog-pause-title">
      <div className="cog-overlay__card">
        <NeoSlot mood="wave" />
        <h2 id="cog-pause-title">{t.pausedTitle}</h2>
        <p className="muted">{t.pausedText}</p>
        <button ref={resume} type="button" className="button button--primary cog-wide" onClick={onResume}>
          {t.resume}
        </button>
        <Link className="link-button" to={GAMES_PATH}>
          {t.quit}
        </Link>
        <p className="cog-small muted">{t.quitHint}</p>
      </div>
    </div>
  );
}

/** Écran de jeu : barre du haut, Néo, aire de jeu, et la pause par-dessus. */
export function GameFrame({
  title,
  progress,
  mood,
  message,
  paused,
  onPause,
  onResume,
  children,
}: {
  title: string;
  progress: string;
  mood: NeoMood;
  message: ReactNode;
  paused: boolean;
  onPause: () => void;
  onResume: () => void;
  children: ReactNode;
}) {
  return (
    <>
      <div className="cog-play" inert={paused}>
        <GameTop title={title} progress={progress} onPause={onPause} />
        <NeoSays mood={mood}>{message}</NeoSays>
        <div className="cog-stage">{children}</div>
      </div>
      {paused && <PauseOverlay onResume={onResume} />}
    </>
  );
}

export function GameIntro({
  instrument,
  rules,
  preview,
  note,
  keyboardNote,
  startLabel = t.practice,
  onStart,
}: {
  instrument: PublicInstrument;
  rules: string[];
  preview: ReactNode;
  note?: string;
  /** Masquée sur les écrans tactiles sans clavier. */
  keyboardNote?: string;
  startLabel?: string;
  onStart: () => void;
}) {
  return (
    <section className="cog-intro">
      <GameTop title={instrument.title} />
      <NeoSays mood="wave" big live={false}>
        {instrument.intro ?? instrument.tagline}
      </NeoSays>
      <div className="cog-card cog-how">
        <h2>{t.howTo}</h2>
        <div className="cog-preview" aria-hidden="true">
          {preview}
        </div>
        <ol className="cog-rules">
          {rules.map((rule, index) => (
            <li key={rule}>
              <span className="cog-rules__step" aria-hidden="true">
                {index + 1}
              </span>
              {frenchSpacing(rule)}
            </li>
          ))}
        </ol>
        {note && <p className="cog-small muted">{frenchSpacing(note)}</p>}
        {keyboardNote && <p className="cog-small muted cog-keyboard-note">{frenchSpacing(keyboardNote)}</p>}
      </div>
      <ul className="cog-chips" aria-label={instrument.title}>
        <li>{t.duration(instrument.duration_min)}</li>
        <li>{t.xp(instrument.xp)}</li>
      </ul>
      <button type="button" className="button button--primary cog-wide" onClick={onStart}>
        {startLabel}
      </button>
      {instrument.source_note && (
        <p className="cog-source">
          <span>{t.sourceLabel}</span> {instrument.source_note}
        </p>
      )}
    </section>
  );
}

/** Entre l'entraînement et la vraie partie. */
export function GoScreen({
  title,
  success,
  onGo,
}: {
  title: string;
  success: boolean;
  onGo: () => void;
}) {
  return (
    <section className="cog-intro cog-go">
      <GameTop title={title} />
      <NeoSays mood={success ? 'cheer' : 'happy'} big>
        {success ? t.goPracticeRight : t.goPracticeLater}
      </NeoSays>
      <div className="cog-card">
        <h2>{t.goTitle}</h2>
        <p className="muted">{t.goText}</p>
      </div>
      <button type="button" className="button button--primary cog-wide" onClick={onGo} autoFocus>
        {t.go}
      </button>
    </section>
  );
}
