import { CheckIcon, CrossIcon } from '../../components/Icons';
import type { Clan, PsyCursor, PsyRun } from '../types';
import { bo } from './backoffice.fr';
import { cursorAnchor } from './CursorSection';
import { cursorName, formatLongDate, headlineText, lowerFirst } from './format';
import { Flag } from './parts';

/**
 * Détail donné dans le quiz. `original_value` et `updated_at` arrivent avec la nouvelle
 * version de l'API : sans eux, on affiche simplement la valeur actuelle.
 */
export interface FactView {
  key: string;
  label: string;
  value: string;
  edited?: boolean;
  hidden?: boolean;
  original_value?: string | null;
  updated_at?: string | null;
}

function changed(fact: FactView): fact is FactView & { original_value: string } {
  return Boolean(fact.edited && fact.original_value && fact.original_value !== fact.value);
}

/** « Mécanique → Le skate et la mécanique (modifiée le 19 novembre 2026) ». */
function FactValue({ fact }: { fact: FactView }) {
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
      {fact.updated_at && (
        <span className="bog-change__date">({bo.facts.editedOn(formatLongDate(fact.updated_at))})</span>
      )}
    </span>
  );
}

function CursorLinks({ cursors }: { cursors: PsyCursor[] }) {
  return (
    <ul className="plain-list bog-reaction__items">
      {cursors.map((cursor) => (
        <li key={cursor.id}>
          <a href={`#${cursorAnchor(cursor.id)}`}>{headlineText(cursor) ?? cursorName(cursor)}</a>
          {cursor.kind === 'bipolar' && <span className="bog-reaction__axis">{cursorName(cursor)}</span>}
        </li>
      ))}
    </ul>
  );
}

/** Ce que le jeune conteste, approuve, corrige ou masque : de quoi ouvrir la discussion. */
export function YouthReactions({ cursors, facts }: { cursors: PsyCursor[]; facts: FactView[] }) {
  const t = bo.youth;
  const disagree = cursors.filter((cursor) => cursor.verdict === 'disagree');
  const agree = cursors.filter((cursor) => cursor.verdict === 'agree');
  const edited = facts.filter((fact) => fact.edited);
  const hidden = facts.filter((fact) => fact.hidden);
  const nothing = !disagree.length && !agree.length && !edited.length && !hidden.length;

  return (
    <section className="bog-reactions" aria-labelledby="bog-reactions-title">
      <h3 id="bog-reactions-title">{t.title}</h3>
      {nothing ? (
        <p className="muted">{t.nothing}</p>
      ) : (
        <ul className="plain-list bog-reactions__list">
          {disagree.length > 0 && (
            <li className="bog-reaction bog-reaction--disagree">
              <span className="bog-reaction__label">
                <CrossIcon />
                {t.disagree}
                <span className="bog-reaction__count">{t.count(disagree.length)}</span>
              </span>
              <CursorLinks cursors={disagree} />
            </li>
          )}
          {agree.length > 0 && (
            <li className="bog-reaction bog-reaction--agree">
              <span className="bog-reaction__label">
                <CheckIcon />
                {t.agree}
                <span className="bog-reaction__count">{t.count(agree.length)}</span>
              </span>
              <CursorLinks cursors={agree} />
            </li>
          )}
          {!disagree.length && !agree.length && (
            <li className="bog-reaction">
              <span className="bog-reaction__label">{bo.cursors.verdict}</span>
              <span className="muted">{t.noVerdict}</span>
            </li>
          )}
          {edited.length > 0 && (
            <li className="bog-reaction bog-reaction--youth">
              <span className="bog-reaction__label">{t.edited}</span>
              <ul className="plain-list bog-reaction__items">
                {edited.map((fact) => (
                  <li key={fact.key}>
                    <span className="bog-reaction__fact">{fact.label}{'\u00a0:'}</span> <FactValue fact={fact} />
                  </li>
                ))}
              </ul>
            </li>
          )}
          {hidden.length > 0 && (
            <li className="bog-reaction bog-reaction--youth">
              <span className="bog-reaction__label">{t.hidden}</span>
              <ul className="plain-list bog-reaction__items">
                {hidden.map((fact) => (
                  <li key={fact.key}>
                    <span className="bog-reaction__fact">{fact.label}{'\u00a0:'}</span> {fact.value}
                  </li>
                ))}
              </ul>
            </li>
          )}
        </ul>
      )}
      <p className="bog-sub">{t.hint}</p>
    </section>
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
              <div key={fact.key} className="bog-fact">
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
