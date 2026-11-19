import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { gameApi } from '../api';
import { ArchetypeBadge } from '../archetype/ArchetypeBadge';
import { isBalancedArchetype } from '../archetype/balanced';
import { frenchSpacing } from '../components/frenchSpacing';
import { gameEmoji } from '../hub/gameEmoji';
import { NeoSlot } from '../hub/NeoSlot';
import { XpBar } from '../hub/XpBar';
import type { CharacterSheet, PublicInstrument, RunResult, YouthTrait } from '../types';
import { playFr } from './play.fr';

const t = playFr;
const SHEET_PATH = '/jeune/fiche';

type SheetGroups = CharacterSheet['trait_groups'];

/**
 * Ce que montre la fin de partie, selon le jeu. Les autres jeux affichent les points forts
 * renvoyés par l’API (tous jeux confondus).
 */
type ResultView = { kind: 'tools' } | { kind: 'group'; group: string; limit?: number };

const RESULT_VIEWS: Record<string, ResultView> = {
  ton_style: { kind: 'tools' },
  miroir: { kind: 'group', group: 'personality' },
  grand_tri: { kind: 'group', group: 'interests', limit: 3 },
};

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

/** Curseurs de la fiche, relus après la partie. `[]` si la fiche ne répond pas. */
function useSheetGroups(enabled: boolean) {
  const [groups, setGroups] = useState<SheetGroups | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    gameApi
      .sheet(controller.signal)
      .then((sheet) => setGroups(sheet.trait_groups))
      .catch(() => {
        if (!controller.signal.aborted) setGroups([]);
      });
    return () => controller.abort();
  }, [enabled]);

  return groups;
}

/** « Entre les deux » dit plus en nommant les deux bouts du curseur. */
const BALANCED_LABEL = 'Entre les deux';

function leaningLabel(trait: YouthTrait) {
  return trait.label === BALANCED_LABEL && trait.low && trait.high
    ? t.result.leaning(trait.low, trait.high)
    : trait.label;
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

function Highlight({ trait, showGroup = true }: { trait: YouthTrait; showGroup?: boolean }) {
  const bipolar = trait.kind === 'bipolar';
  return (
    <li className={`play-highlight${bipolar ? '' : ' play-highlight--strength'}`}>
      {showGroup && <span className="play-highlight__group">{t.groups[trait.group] ?? ''}</span>}
      <strong className="play-highlight__label">
        {!bipolar && <span aria-hidden="true">★ </span>}
        {leaningLabel(trait)}
      </strong>
      {bipolar && <Leaning trait={trait} />}
    </li>
  );
}

function TraitPanel({
  id,
  title,
  hint,
  traits,
  showGroup,
}: {
  id: string;
  title: string;
  hint: string;
  traits: YouthTrait[];
  showGroup: boolean;
}) {
  return (
    <section className="play-panel" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      <ul className="play-highlights">
        {traits.map((trait) => (
          <Highlight key={trait.id} trait={trait} showGroup={showGroup} />
        ))}
      </ul>
      <p className="play-panel__hint">{hint}</p>
    </section>
  );
}

function StyleTools({ traits }: { traits: Record<string, YouthTrait> }) {
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
                    <strong className="play-tool__label">{leaningLabel(trait)}</strong>
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

/** Ce qui ressort : propre au jeu si possible, sinon les points forts tous jeux confondus. */
function WhatStandsOut({
  instrumentId,
  highlights,
}: {
  instrumentId: string;
  highlights: YouthTrait[];
}) {
  const view = RESULT_VIEWS[instrumentId];
  const groups = useSheetGroups(view !== undefined);

  if (view && groups === null) return null;
  if (view?.kind === 'tools' && groups?.length) {
    const all = groups.flatMap((group) => group.traits);
    return <StyleTools traits={Object.fromEntries(all.map((trait) => [trait.id, trait]))} />;
  }
  if (view?.kind === 'group') {
    const group = groups?.find((entry) => entry.id === view.group);
    const known = (group?.traits ?? []).filter((trait) => trait.value !== null);
    const traits = known.slice(0, view.limit);
    if (group && traits.length) {
      return (
        <TraitPanel
          id="play-group-title"
          title={t.result.views[view.group] ?? group.label}
          hint={t.result.highlightsHint}
          traits={traits}
          showGroup={false}
        />
      );
    }
  }
  if (!highlights.length) return null;
  return (
    <TraitPanel
      id="play-highlights-title"
      title={t.result.highlights}
      hint={t.result.highlightsHint}
      traits={highlights}
      showGroup
    />
  );
}

/** L'archétype suit le trait de caractère le plus marqué : une partie peut le faire changer. */
function ArchetypeChange({ result }: { result: RunResult }) {
  const { archetype, previous_archetype: previous } = result;
  if (!archetype || !previous) return null;
  return (
    <section className="play-panel play-archetype" aria-labelledby="play-archetype-title">
      <h2 id="play-archetype-title">{t.result.archetypeTitle}</h2>
      <ArchetypeBadge archetype={archetype} size="medium" caption />
      <p className="play-archetype__before">{frenchSpacing(t.result.archetypeBefore(previous.name))}</p>
      <p className="play-panel__hint">
        {frenchSpacing(isBalancedArchetype(archetype) ? t.result.archetypeHintBalanced : t.result.archetypeHint)}
      </p>
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

      <ArchetypeChange result={result} />

      <WhatStandsOut instrumentId={instrument.id} highlights={result.highlights} />

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
