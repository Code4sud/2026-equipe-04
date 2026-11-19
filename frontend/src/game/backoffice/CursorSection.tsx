import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, Loading } from '../../components/Feedback';
import type { PsyCursor, PsyOverview, PsyRun, PsyTraitDetail, PsyTraitSignal, Tier } from '../types';
import { bo } from './backoffice.fr';
import { CursorBar } from './CursorBar';
import {
  TIER_ORDER,
  cursorName,
  describeValue,
  disagreesNow,
  formatNumber,
  formatPercent,
  formatShortDate,
  frenchSpacing,
  headlineText,
  performanceMetrics,
  tierRank,
  tierWeight,
} from './format';
import { useMethod } from './method';
import { Chevron, Flag, Missing, TierChip, VerdictCell } from './parts';
import type { Detail, Details } from './useDetails';

const t = bo.cursors;

export type CursorGroup = NonNullable<PsyOverview['cursor_groups']>[number];
/** Le drapeau existe dans la nouvelle version de l'API : on le lit s'il est là. */
type TraitSignal = PsyTraitSignal & { hidden_by_youth?: boolean };

export function cursorAnchor(cursorId: string) {
  return `bog-cursor-${cursorId}`;
}

export function TierLegend() {
  const { weights, thresholds } = useMethod();
  return (
    <div className="bog-legend">
      <p>{t.legend}</p>
      <ul className="plain-list">
        {TIER_ORDER.map((tier) => (
          <li key={tier}>
            <TierChip tier={tier} /> {formatNumber(weights[tier])}
          </li>
        ))}
      </ul>
      <Link to="/psy/sources" className="bog-link">
        {bo.panel.sources}
      </Link>
      <p className="bog-legend__note">
        {t.confidenceLegend(formatNumber(thresholds.medium), formatNumber(thresholds.high))}
      </p>
    </div>
  );
}

function CursorResult({ cursor }: { cursor: PsyCursor }) {
  const headline = headlineText(cursor);
  return (
    <div className="bog-result">
      <p className={headline ? 'bog-headline' : 'bog-headline bog-headline--empty'}>{headline ?? t.noData}</p>
      <CursorBar cursor={cursor} />
      {cursor.n > 0 && cursor.confidence !== 'none' && (
        <p className="bog-sub">
          {t.answers(cursor.n)} · {t.confidence(cursor.confidence)}
        </p>
      )}
      {cursor.norm_note && <p className="bog-note">{cursor.norm_note}</p>}
    </div>
  );
}

function TierBreakdown({ cursor }: { cursor: PsyCursor }) {
  const tiers = (Object.keys(cursor.by_tier) as Tier[]).sort((a, b) => tierRank(a) - tierRank(b));
  if (tiers.length === 0) return <Missing label={t.noData} />;
  return (
    <ul className="plain-list bog-tiers">
      {tiers.map((tier) => {
        const entry = cursor.by_tier[tier];
        if (!entry) return null;
        return (
          <li key={tier}>
            <TierChip tier={tier} label={entry.label} />
            <span className="bog-tiers__value">
              {entry.value === null ? t.noData : describeValue(cursor, entry.value)}
              <span className="bog-tiers__count">{t.answers(entry.n)}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function SignalRow({
  cursor,
  signal,
  total,
  run,
}: {
  cursor: PsyCursor;
  signal: TraitSignal;
  total: number;
  run: PsyRun | undefined;
}) {
  const { weights } = useMethod();
  const talent = signal.tier === 'talent';
  const levelWeight = tierWeight(signal.tier, weights);
  const effective = signal.weight * levelWeight;
  const metrics = run ? performanceMetrics(run.metrics) : [];

  let origin = signal.instrument_title ?? signal.instrument_id ?? bo.runs.unknownInstrument;
  if (talent) origin = t.talentSource;

  let answer = signal.answer ? <span>{frenchSpacing(signal.answer)}</span> : <Missing />;
  if (talent && signal.answer) {
    answer = <span className="bog-quote">{`«\u00a0${signal.answer}\u00a0»`}</span>;
  } else if (!signal.item_id && !signal.answer && metrics.length > 0) {
    answer = <span>{metrics.map((metric) => `${metric.label}\u00a0: ${metric.value}`).join(' · ')}</span>;
  }

  return (
    <tr>
      <th scope="row">
        <span className="bog-strong">{origin}</span>
        <TierChip tier={signal.tier} label={signal.tier_label} />
      </th>
      <td>
        {talent && t.talent(signal.prompt ?? '')}
        {!talent && (signal.prompt ? frenchSpacing(signal.prompt) : <span className="muted">{t.runScore}</span>)}
      </td>
      <td>
        {answer}
        {signal.hidden_by_youth && <Flag tone="youth">{bo.run.hidden}</Flag>}
        {talent && <span className="bog-sub">{t.talentHistory}</span>}
      </td>
      <td>
        {describeValue(cursor, signal.value)}
        <span className="bog-sub">{t.position(formatNumber(signal.value))}</span>
      </td>
      <td>
        {formatNumber(effective)}
        <span className="bog-sub">{t.weightDetail(formatNumber(signal.weight), formatNumber(levelWeight))}</span>
        {total > 0 && <span className="bog-sub">{t.share(formatPercent((effective / total) * 100))}</span>}
      </td>
      <td className="bog-date">{signal.at ? formatShortDate(signal.at) : <Missing />}</td>
    </tr>
  );
}

function CursorDetail({
  cursor,
  detail,
  runs,
  onRetry,
}: {
  cursor: PsyCursor;
  detail: Detail<PsyTraitDetail>;
  runs: Map<string, PsyRun>;
  onRetry: () => void;
}) {
  const { weights } = useMethod();
  if (detail.state === 'loading') return <Loading />;
  if (detail.state === 'error') return <ErrorState message={detail.message} onRetry={onRetry} />;

  const current = detail.data.cursor ?? cursor;
  const signals: TraitSignal[] = detail.data.signals;
  const total = signals.reduce((sum, signal) => sum + signal.weight * tierWeight(signal.tier, weights), 0);
  const name = cursorName(current);
  const meta = [
    current.reference ? t.reference(current.reference) : null,
    current.kind === 'bipolar' && current.low && current.high ? t.scale(current.low, current.high) : null,
    t.basis(current.value === null ? null : formatNumber(current.value), current.n),
  ].filter(Boolean);

  return (
    <div className="bog-detail">
      <div className="bog-detail__intro">
        {current.description && <p>{current.description}</p>}
        <p className="bog-sub">{meta.join(' ')}</p>
      </div>
      {signals.length === 0 ? (
        <p className="empty">{t.empty}</p>
      ) : (
        <div className="table-wrap">
          <table className="table table--stack bog-table bog-signals">
            <caption className="visually-hidden">{t.signalsCaption(name)}</caption>
            <colgroup>
              <col className="bog-col-origin" />
              <col className="bog-col-question" />
              <col className="bog-col-answer" />
              <col className="bog-col-value" />
              <col className="bog-col-weight" />
              <col className="bog-col-date" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{t.origin}</th>
                <th scope="col">{t.question}</th>
                <th scope="col">{t.answer}</th>
                <th scope="col">{t.signalValue}</th>
                <th scope="col">{t.weight}</th>
                <th scope="col">{t.date}</th>
              </tr>
            </thead>
            <tbody>
              {signals.map((signal, index) => (
                <SignalRow
                  key={`${signal.run_id ?? 'talent'}-${signal.item_id ?? 'run'}-${index}`}
                  cursor={current}
                  signal={signal}
                  total={total}
                  run={signal.run_id ? runs.get(signal.run_id) : undefined}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CursorRow({
  cursor,
  detail,
  onLoad,
  runs,
}: {
  cursor: PsyCursor;
  detail: Detail<PsyTraitDetail> | undefined;
  onLoad: (id: string) => Promise<boolean>;
  runs: Map<string, PsyRun>;
}) {
  const [open, setOpen] = useState(false);
  const name = cursorName(cursor);
  const detailId = `${cursorAnchor(cursor.id)}-detail`;
  const canOpen = cursor.n > 0;
  const classes = [
    disagreesNow(cursor) ? 'bog-row--disagree' : '',
    cursor.value === null ? 'bog-row--empty' : '',
  ].join(' ');

  function toggle() {
    if (!open) void onLoad(cursor.id);
    setOpen(!open);
  }

  return (
    <>
      <tr id={cursorAnchor(cursor.id)} className={classes.trim() || undefined}>
        <th scope="row">
          <span className="bog-name">{name}</span>
          {cursor.reference && <span className="table__ref">{cursor.reference}</span>}
          {canOpen && (
            <button
              type="button"
              className="bog-toggle"
              aria-expanded={open}
              aria-controls={detailId}
              onClick={toggle}
            >
              {open ? t.hide : t.show}
              <span className="visually-hidden"> : {name}</span>
              <Chevron />
            </button>
          )}
        </th>
        <td>
          <CursorResult cursor={cursor} />
        </td>
        <td>
          <TierBreakdown cursor={cursor} />
        </td>
        <td>
          <VerdictCell cursor={cursor} />
        </td>
      </tr>
      {canOpen && (
        <tr id={detailId} className="bog-detail-row" hidden={!open} data-loaded={detail ? '' : undefined}>
          <td colSpan={4}>
            {detail && (
              <CursorDetail
                cursor={cursor}
                detail={detail}
                runs={runs}
                onRetry={() => void onLoad(cursor.id)}
              />
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export function CursorSection({
  groups,
  traits,
  runs,
}: {
  groups: CursorGroup[];
  traits: Details<PsyTraitDetail>;
  runs: Map<string, PsyRun>;
}) {
  return (
    <section className="bog-section" aria-labelledby="bog-cursors-title">
      <h3 id="bog-cursors-title">{t.title}</h3>
      <TierLegend />
      {groups.map((group) => (
        <div key={group.id} className="table-wrap">
          <table className="table table--stack bog-table bog-cursors">
            <caption>{group.label}</caption>
            <colgroup>
              <col className="bog-col-name" />
              <col className="bog-col-result" />
              <col className="bog-col-evidence" />
              <col className="bog-col-verdict" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{t.cursor}</th>
                <th scope="col">{t.result}</th>
                <th scope="col">{t.evidence}</th>
                <th scope="col">{t.verdict}</th>
              </tr>
            </thead>
            <tbody>
              {group.cursors.map((cursor) => (
                <CursorRow
                  key={cursor.id}
                  cursor={cursor}
                  detail={traits.details[cursor.id]}
                  onLoad={traits.load}
                  runs={runs}
                />
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
