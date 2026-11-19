import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { gameApi } from '../api';
import { gameEmoji } from '../hub/gameEmoji';
import { NeoSlot } from '../hub/NeoSlot';
import { XpBar } from '../hub/XpBar';
import type { PublicInstrument, RunResult, YouthTrait } from '../types';
import { playFr } from './play.fr';

const t = playFr;
const STYLE_GAME_ID = 'ton_style';
const SHEET_PATH = '/jeune/fiche';

function prefersReducedMotion() {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

/** Fait défiler le compteur d’XP, sauf si le jeune a demandé moins d’animations. */
function useCountUp(target: number, duration = 900) {
  const [value, setValue] = useState(() => (prefersReducedMotion() ? target : 0));

  useEffect(() => {
    if (prefersReducedMotion()) {
      setValue(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      setValue(Math.round(target * (1 - (1 - progress) ** 3)));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return value;
}

/** Curseur neutre : les deux bouts sont des qualités, aucun n’est un score bas. */
function Leaning({ trait }: { trait: YouthTrait }) {
  if (trait.value === null || !trait.low || !trait.high) return null;
  return (
    <div className="play-leaning">
      <span className="play-leaning__track" aria-hidden="true">
        <span className="play-leaning__dot" style={{ left: `${trait.value}%` }} />
      </span>
      <span className="play-leaning__ends">
        <span>{trait.low}</span>
        <span>{trait.high}</span>
      </span>
    </div>
  );
}

function Highlight({ trait }: { trait: YouthTrait }) {
  const bipolar = trait.kind === 'bipolar';
  return (
    <li className={`play-highlight${bipolar ? '' : ' play-highlight--strength'}`}>
      <span className="play-highlight__group">{t.groups[trait.group] ?? ''}</span>
      <strong className="play-highlight__label">
        {!bipolar && <span aria-hidden="true">★ </span>}
        {trait.label}
      </strong>
      {bipolar && <Leaning trait={trait} />}
    </li>
  );
}

function StyleTools() {
  const [traits, setTraits] = useState<Record<string, YouthTrait> | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    gameApi
      .sheet(controller.signal)
      .then((sheet) => {
        const all = sheet.trait_groups.flatMap((group) => group.traits);
        setTraits(Object.fromEntries(all.map((trait) => [trait.id, trait])));
      })
      .catch(() => {
        if (!controller.signal.aborted) setTraits({});
      });
    return () => controller.abort();
  }, []);

  if (!traits) return null;
  return (
    <section className="play-panel" aria-labelledby="play-tools-title">
      <h2 id="play-tools-title">{t.result.tools}</h2>
      <ul className="play-tools">
        {t.styleTools.map((tool) => {
          const trait = traits[tool.trait];
          return (
            <li key={tool.trait} className="play-tool">
              <span className="play-tool__icon" aria-hidden="true">
                {tool.emoji}
              </span>
              <div className="play-tool__body">
                <span className="play-tool__name">{tool.name}</span>
                {trait && trait.value !== null ? (
                  <>
                    <strong className="play-tool__label">{trait.label}</strong>
                    <Leaning trait={trait} />
                  </>
                ) : (
                  <span className="play-tool__empty">{t.result.notYet}</span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="play-panel__hint">{t.result.toolsHint}</p>
    </section>
  );
}

interface Props {
  instrument: PublicInstrument;
  result: RunResult;
  /** XP déjà gagnés réponse après réponse pendant cette partie. */
  answerXp: number;
  exitTo: string;
}

export function RunResults({ instrument, result, answerXp, exitTo }: Props) {
  const total = answerXp + result.xp_gained;
  const shown = useCountUp(total);
  const heading = useRef<HTMLHeadingElement>(null);
  const isStyle = instrument.id === STYLE_GAME_ID;

  useEffect(() => {
    window.scrollTo({ top: 0 });
    heading.current?.focus({ preventScroll: true });
  }, []);

  return (
    <div className="play play--result">
      <div className="play-hero">
        <h1 ref={heading} tabIndex={-1}>
          {t.result.title}
        </h1>
      </div>
      {instrument.outro && (
        <div className="play-says">
          <NeoSlot mood="cheer" />
          <p className="play-bubble">{instrument.outro}</p>
        </div>
      )}

      <section className="play-panel play-panel--xp" aria-labelledby="play-xp-title">
        <h2 id="play-xp-title" className="play-kicker">
          {t.result.xpTitle}
        </h2>
        <p className="play-xp-total">
          <span aria-hidden="true">+{shown} XP</span>
          <span className="visually-hidden">{t.result.xpSpoken(total)}</span>
        </p>
        {result.leveled_up && (
          <p className="play-levelup" role="status">
            <span aria-hidden="true">🎉 </span>
            <strong>{t.result.levelUp(result.progress.level)}</strong>{' '}
            {t.result.levelTitle(result.progress.level_title)}
          </p>
        )}
        <XpBar progress={result.progress} />
      </section>

      {result.new_badges.length > 0 && (
        <section className="play-panel" aria-labelledby="play-badges-title">
          <h2 id="play-badges-title">{t.result.badges(result.new_badges.length)}</h2>
          <ul className="play-badges">
            {result.new_badges.map((badge) => (
              <li key={badge.id} className="play-badge">
                <span className="play-badge__icon" aria-hidden="true">
                  {gameEmoji(badge.icon)}
                </span>
                <span>
                  <strong>{badge.label}</strong>
                  <small>{badge.description}</small>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {isStyle ? (
        <StyleTools />
      ) : (
        result.highlights.length > 0 && (
          <section className="play-panel" aria-labelledby="play-highlights-title">
            <h2 id="play-highlights-title">{t.result.highlights}</h2>
            <ul className="play-highlights">
              {result.highlights.map((trait) => (
                <Highlight key={trait.id} trait={trait} />
              ))}
            </ul>
            <p className="play-panel__hint">{t.result.highlightsHint}</p>
          </section>
        )
      )}

      <div className="play-actions">
        <Link to={exitTo} className="button button--primary">
          {t.result.hub}
        </Link>
        <Link to={SHEET_PATH} className="button">
          {t.result.sheet}
        </Link>
      </div>
    </div>
  );
}
