import type { Clan, PsyCursor, PsyRun } from '../types';
import { bo } from './backoffice.fr';
import { cursorName, formatLongDate, headlineText, lowerFirst } from './format';
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

export function Summary({
  clan,
  progress,
  runs,
  cursors,
  facts,
}: {
  clan: Clan | null | undefined;
  progress: { xp: number; level: number; level_title: string } | undefined;
  runs: PsyRun[];
  cursors: PsyCursor[];
  facts: FactView[];
}) {
  const t = bo.summary;
  const completed = runs.filter((run) => run.status === 'completed').length;
  const open = runs.length - completed;
  const last = latestActivity(runs);
  const clanCursor = clan ? cursors.find((cursor) => cursor.id === clan.trait) : undefined;
  const clanText = clanCursor ? (headlineText(clanCursor) ?? lowerFirst(cursorName(clanCursor))) : null;

  return (
    <section className="bog-section" aria-labelledby="bog-summary-title">
      <h3 id="bog-summary-title">{t.title}</h3>
      <dl className="bog-summary">
        <div>
          <dt>{t.clan}</dt>
          <dd>
            <strong>{clan?.name ?? t.noClan}</strong>
            {clanText && <span className="bog-sub">{t.clanBasis(clanText)}</span>}
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
