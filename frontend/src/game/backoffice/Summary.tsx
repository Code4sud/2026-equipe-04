import { ArchetypeBadge } from '../archetype/ArchetypeBadge';
import type { PsyArchetype, PsyCursor, PsyRun } from '../types';
import { bo } from './backoffice.fr';
import { formatLongDate, formatPercent, headlineText, lowerFirst } from './format';
import { Flag } from './parts';

/**
 * Détail donné dans le quiz. `original_value` et `edited_at` peuvent manquer si une ancienne
 * version de l'API répond : on affiche alors simplement la valeur actuelle.
 */
export interface FactView {
  key: string;
  label: string;
  value: string;
  edited?: boolean;
  hidden?: boolean;
  original_value?: string | null;
  updated_at?: string | null;
  /** Dernière correction de la valeur par le jeune ; masquer ou remontrer n'en est pas une. */
  edited_at?: string | null;
}

export function factAnchor(key: string) {
  return `bog-fact-${key}`;
}

function changed(fact: FactView): fact is FactView & { original_value: string } {
  return Boolean(fact.edited && fact.original_value && fact.original_value !== fact.value);
}

/** « Mécanique → Le skate et la mécanique (modifiée le 19 novembre 2026) ». */
export function FactValue({ fact }: { fact: FactView }) {
  if (!changed(fact)) return <span className="bog-fact__value">{fact.value}</span>;
  return (
    <span className="bog-change">
      <span className="visually-hidden">{bo.facts.original} </span>
      <span className="bog-change__old">{fact.original_value}</span>
      <span className="bog-change__arrow" aria-hidden="true">
        →
      </span>
      <span className="visually-hidden">, {bo.facts.current} </span>
      <span className="bog-fact__value">{fact.value}</span>
      {fact.edited_at && (
        <span className="bog-change__date">({bo.facts.editedOn(formatLongDate(fact.edited_at))})</span>
      )}
    </span>
  );
}

function latestActivity(runs: PsyRun[]): string | null {
  let latest: string | null = null;
  for (const run of runs) {
    for (const date of [run.completed_at, run.paused_at, run.started_at]) {
      if (date && (!latest || new Date(date) > new Date(latest))) latest = date;
    }
  }
  return latest;
}

/**
 * D'après quoi l'archétype a été attribué : le titre du curseur qui l'a désigné (« 72 % sociable »),
 * repris du tableau des curseurs pour dire exactement la même chose, ou recalculé de sa valeur.
 */
function archetypeBasis(archetype: PsyArchetype, cursors: PsyCursor[]): string {
  const t = bo.summary;
  if (archetype.pole === 'balanced' || archetype.value === null) return t.archetypeBalanced;
  const cursor = cursors.find((item) => item.id === archetype.trait);
  const percent = archetype.pole === 'low' ? 100 - archetype.value : archetype.value;
  const headline = (cursor && headlineText(cursor)) ?? `${formatPercent(percent)} ${lowerFirst(archetype.pole_label)}`;
  return t.archetypeBasis(headline);
}

export function Summary({
  archetype,
  progress,
  runs,
  cursors,
  facts,
}: {
  archetype: PsyArchetype | null | undefined;
  progress: { xp: number; level: number; level_title: string } | undefined;
  runs: PsyRun[];
  cursors: PsyCursor[];
  facts: FactView[];
}) {
  const t = bo.summary;
  const completed = runs.filter((run) => run.status === 'completed').length;
  const open = runs.length - completed;
  const last = latestActivity(runs);

  return (
    <section className="bog-section" aria-labelledby="bog-summary-title">
      <h3 id="bog-summary-title">{t.title}</h3>
      <dl className="bog-summary">
        <div className="bog-summary__archetype">
          <dt>{t.archetype}</dt>
          <dd>
            {archetype ? (
              <>
                <span className="bog-archetype">
                  <ArchetypeBadge archetype={archetype} size="small" />
                  <strong>{archetype.name}</strong>
                </span>
                <span className="bog-sub">{archetypeBasis(archetype, cursors)}</span>
              </>
            ) : (
              <strong>{t.noArchetype}</strong>
            )}
          </dd>
        </div>
        <div>
          <dt>{t.level}</dt>
          <dd>
            <strong>{progress ? t.levelValue(progress.level, progress.level_title) : '1'}</strong>
            {progress && <span className="bog-sub">{t.xp(progress.xp)}</span>}
          </dd>
        </div>
        <div>
          <dt>{t.completed}</dt>
          <dd>
            <strong>{completed}</strong>
            {open > 0 && <span className="bog-sub">{t.inProgress(open)}</span>}
          </dd>
        </div>
        <div>
          <dt>{t.lastActivity}</dt>
          <dd>
            <strong>{last ? formatLongDate(last) : t.noActivity}</strong>
          </dd>
        </div>
      </dl>

      <div className="bog-facts-block">
        <div className="bog-facts-block__head">
          <h4>{bo.facts.title}</h4>
          <p className="bog-sub">{bo.facts.hint}</p>
        </div>
        {facts.length === 0 ? (
          <p className="empty">{bo.facts.empty}</p>
        ) : (
          <dl className="bog-facts">
            {facts.map((fact) => (
              <div key={fact.key} id={factAnchor(fact.key)} className="bog-fact">
                <dt>{fact.label}</dt>
                <dd>
                  <FactValue fact={fact} />
                  {(fact.edited || fact.hidden) && (
                    <span className="bog-flags">
                      {fact.edited && <Flag tone="youth">{bo.facts.edited}</Flag>}
                      {fact.hidden && <Flag tone="youth">{bo.facts.hidden}</Flag>}
                    </span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}
