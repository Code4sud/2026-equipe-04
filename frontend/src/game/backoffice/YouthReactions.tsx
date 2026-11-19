import { useId, useState } from 'react';
import { CheckIcon, CrossIcon } from '../../components/Icons';
import type { GameEvent, PsyCursor, PsyRun } from '../types';
import { bo } from './backoffice.fr';
import { cursorAnchor } from './CursorSection';
import { describeEvent, type EventLine } from './events';
import { cursorName, describeSignal, formatMoment, frenchSpacing, headlineText } from './format';
import { Chevron, Flag } from './parts';
import { runAnchor } from './RunSection';
import { FactValue, factAnchor, type FactView } from './Summary';

const t = bo.youth;
const e = bo.events;
/** Les dernières modifications d'abord ; le reste se déplie, et s'imprime toujours. */
const RECENT_EVENTS = 6;

/** Ce que le jeune a jugé (« 72 % réservé »), sinon le résultat actuel du curseur. */
function judgedText(cursor: PsyCursor): string {
  const value = cursor.verdict_detail?.value_at_verdict;
  if (typeof value === 'number') return describeSignal(cursor, value);
  return headlineText(cursor) ?? cursorName(cursor);
}

function CursorLinks({ cursors }: { cursors: PsyCursor[] }) {
  return (
    <ul className="plain-list bog-reaction__items">
      {cursors.map((cursor) => {
        const detail = cursor.verdict_detail;
        return (
          <li key={cursor.id}>
            <a href={`#${cursorAnchor(cursor.id)}`}>{judgedText(cursor)}</a>
            {cursor.kind === 'bipolar' && <span className="bog-reaction__axis">{cursorName(cursor)}</span>}
            {detail?.stale && <Flag>{t.stale(detail.label_at_verdict ?? cursorName(cursor))}</Flag>}
          </li>
        );
      })}
    </ul>
  );
}

function Change({ change }: { change: NonNullable<EventLine['change']> }) {
  return (
    <>
      <span className="visually-hidden">{e.before} </span>
      <span className="bog-change__old">{frenchSpacing(change.before)}</span>
      <span className="bog-change__arrow" aria-hidden="true">
        →
      </span>
      <span className="visually-hidden">{e.after} </span>
      <span className="bog-event__new">{frenchSpacing(change.after)}</span>
    </>
  );
}

interface Targets {
  cursors: Map<string, PsyCursor>;
  runs: Map<string, PsyRun>;
  facts: Set<string>;
}

/** Lien vers ce que l'événement concerne, s'il est encore affiché dans la fiche. */
function targetOf(event: GameEvent, targets: Targets): string | null {
  const ref = event.ref;
  if (ref.type === 'fact') return targets.facts.has(ref.key) ? `#${factAnchor(ref.key)}` : null;
  if (ref.type === 'trait') return targets.cursors.has(ref.trait_id) ? `#${cursorAnchor(ref.trait_id)}` : null;
  if (ref.type === 'answer') return targets.runs.has(ref.run_id) ? `#${runAnchor(ref.run_id)}` : null;
  return null;
}

function EventItem({ event, targets, hidden }: { event: GameEvent; targets: Targets; hidden: boolean }) {
  const cursor = event.ref.type === 'trait' ? targets.cursors.get(event.ref.trait_id) : undefined;
  const line = describeEvent(event, cursor);
  const href = targetOf(event, targets);
  const subject = frenchSpacing(event.subject);

  return (
    <li className="bog-event" hidden={hidden}>
      <time className="bog-event__time" dateTime={event.at}>
        {formatMoment(event.at)}
      </time>
      <div className="bog-event__body">
        <p className="bog-event__title">
          <span className="bog-event__action">
            {line.action}
            <span className="visually-hidden">{'\u00a0:'}</span>
          </span>{' '}
          {href ? <a href={href}>{subject}</a> : subject}
        </p>
        {(line.change || line.detail) && (
          <p className="bog-event__change">
            {line.change && <Change change={line.change} />}
            {line.change && line.detail && ' '}
            {line.detail && frenchSpacing(line.detail)}
          </p>
        )}
        {line.note && <p className="bog-sub">{frenchSpacing(line.note)}</p>}
      </div>
    </li>
  );
}

/** Chaque modification du jeune, datée, de la plus récente à la plus ancienne. */
function EventHistory({ events, targets }: { events: GameEvent[]; targets: Targets }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const listId = `${id}-list`;
  const titleId = `${id}-title`;

  return (
    <section className="bog-history" aria-labelledby={titleId}>
      <div className="bog-history__head">
        <h4 id={titleId}>{e.title}</h4>
        <p className="bog-sub">{e.hint}</p>
      </div>
      <ol id={listId} className="plain-list bog-events">
        {events.map((event, index) => (
          <EventItem key={event.id} event={event} targets={targets} hidden={!open && index >= RECENT_EVENTS} />
        ))}
      </ol>
      {events.length > RECENT_EVENTS && (
        <button
          type="button"
          className="bog-toggle"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen(!open)}
        >
          {open ? e.less : e.more(events.length)}
          <Chevron />
        </button>
      )}
    </section>
  );
}

/** Ce que le jeune conteste, approuve, corrige ou masque, et l'historique de ses changements. */
export function YouthReactions({
  cursors,
  facts,
  events,
  runs,
}: {
  cursors: PsyCursor[];
  facts: FactView[];
  events: GameEvent[];
  runs: Map<string, PsyRun>;
}) {
  const disagree = cursors.filter((cursor) => cursor.verdict === 'disagree');
  const agree = cursors.filter((cursor) => cursor.verdict === 'agree');
  const edited = facts.filter((fact) => fact.edited);
  const hidden = facts.filter((fact) => fact.hidden);
  const nothing = !disagree.length && !agree.length && !edited.length && !hidden.length && !events.length;
  const targets: Targets = {
    cursors: new Map(cursors.map((cursor) => [cursor.id, cursor])),
    runs,
    facts: new Set(facts.map((fact) => fact.key)),
  };

  return (
    <section className="bog-reactions" aria-labelledby="bog-reactions-title">
      <h3 id="bog-reactions-title">{t.title}</h3>
      {nothing ? (
        <p className="muted">{t.nothing}</p>
      ) : (
        <>
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
                      <span className="bog-reaction__fact">
                        {fact.label}
                        {'\u00a0:'}
                      </span>{' '}
                      <FactValue fact={fact} />
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
                      <span className="bog-reaction__fact">
                        {fact.label}
                        {'\u00a0:'}
                      </span>{' '}
                      {fact.value}
                    </li>
                  ))}
                </ul>
              </li>
            )}
          </ul>
          {events.length > 0 && <EventHistory events={events} targets={targets} />}
        </>
      )}
      <p className="bog-sub">{t.hint}</p>
    </section>
  );
}
