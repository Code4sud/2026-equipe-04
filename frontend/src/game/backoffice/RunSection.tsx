import { useState, type ReactNode } from 'react';
import { ErrorState, Loading } from '../../components/Feedback';
import { formatDateTime } from '../../components/format';
import type {
  GameSource,
  InstrumentInfo,
  ItemSourceRef,
  PsyAnswerRow,
  PsyCursor,
  PsyRun,
  PsyRunDetail,
  SignalRow,
} from '../types';
import { bo } from './backoffice.fr';
import {
  cursorName,
  describeSignal,
  describeValue,
  formatDuration,
  formatNumber,
  formatPercent,
  frenchSpacing,
  median,
  performanceMetrics,
  scaleScores,
  tierWeight,
  trialDetail,
} from './format';
import { useMethod } from './method';
import { Chevron, Flag, Missing, SourceDetails, TierChip } from './parts';
import type { Detail, Details } from './useDetails';

const t = bo.runs;
const r = bo.run;

/** `chapters` peut manquer si une ancienne version de l'API répond. */
type InstrumentView = Omit<InstrumentInfo, 'chapters'> & Partial<Pick<InstrumentInfo, 'chapters'>>;
type Cursors = Map<string, PsyCursor>;

export function runAnchor(runId: string) {
  return `bog-run-${runId}`;
}

function chapterTitle(instrument: InstrumentView | null, chapter: string): string {
  const found = instrument?.chapters?.find((item) => item.id === chapter);
  if (found) return found.title;
  const text = chapter.replace(/[_-]+/g, ' ');
  return text.charAt(0).toLocaleUpperCase('fr-FR') + text.slice(1);
}

function runStatus(run: PsyRun) {
  if (run.status === 'completed') return 'completed' as const;
  return run.paused_at ? ('paused' as const) : ('in_progress' as const);
}

function quoted(text: string) {
  return `«\u00a0${text}\u00a0»`;
}

function MetricList({ metrics }: { metrics: ReturnType<typeof performanceMetrics> }) {
  return (
    <dl className="bog-metrics">
      {metrics.map((metric) => (
        <div key={metric.key}>
          <dt>{metric.label}</dt>
          <dd>{metric.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function RunScores({ run, cursors }: { run: PsyRun; cursors: Cursors }) {
  const scales = scaleScores(run.metrics);
  if (scales.length > 0) {
    return (
      <ul className="plain-list bog-scores">
        {scales.map(([trait, scale]) => {
          const cursor = cursors.get(trait);
          return (
            <li key={trait}>
              <span className="bog-scores__name">{cursor ? cursorName(cursor) : trait}</span>
              <span>
                {t.rawScore(formatNumber(scale.raw_sum), formatNumber(scale.raw_min), formatNumber(scale.raw_max))}
                , {cursor ? describeValue(cursor, scale.percent) : formatPercent(scale.percent)}
                <span className="bog-scores__count">{t.items(scale.n)}</span>
              </span>
            </li>
          );
        })}
      </ul>
    );
  }
  const metrics = performanceMetrics(run.metrics);
  if (metrics.length > 0) return <MetricList metrics={metrics} />;
  return <span className="muted">{t.noScore}</span>;
}

/** `tier` : niveau de l'instrument ; un signal qui porte un autre niveau le montre à côté de lui. */
function SignalList({ signals, cursors, tier }: { signals: SignalRow[]; cursors: Cursors; tier?: string }) {
  if (signals.length === 0) return <Missing label={r.noSignal} />;
  return (
    <ul className="plain-list bog-signal-list">
      {signals.map((signal, index) => {
        const cursor = cursors.get(signal.trait);
        const text = cursor
          ? describeSignal(cursor, signal.value)
          : `${signal.trait_label ?? signal.trait}\u00a0: ${formatNumber(signal.value)}`;
        return (
          <li key={`${signal.trait}-${index}`}>
            {text}
            {signal.weight !== 1 && <span className="bog-weight"> ({bo.weight(formatNumber(signal.weight))})</span>}
            {tier && signal.tier !== tier && (
              <>
                {' '}
                <TierChip tier={signal.tier} />
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}

/** Choix retenus : un identifiant, une liste pour plusieurs choix, aucun pour une réponse libre. */
function chosenIds(value: unknown): Set<string> {
  if (typeof value === 'string') return new Set([value]);
  if (Array.isArray(value)) return new Set(value.filter((id): id is string => typeof id === 'string'));
  return new Set();
}

interface OfferedItem {
  key: string;
  text: string;
  chosen: boolean;
  /** Position sur l'échelle, pour une question Likert. */
  position?: number;
}

function OfferedList({ label, items, scale = false }: { label: string; items: OfferedItem[]; scale?: boolean }) {
  return (
    <ul className={scale ? 'plain-list bog-offered bog-offered--scale' : 'plain-list bog-offered'} aria-label={label}>
      {items.map((item) => (
        <li key={item.key} className="bog-offered__item">
          <span className={item.chosen ? 'bog-offered__label is-chosen' : 'bog-offered__label'}>
            {item.position !== undefined && <span className="bog-offered__position">{item.position}</span>}
            {frenchSpacing(item.text)}
            {item.chosen && <span className="visually-hidden"> {r.chosen}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Ce qui était proposé au jeune, tel qu'il l'a vu : les choix d'une question à choix, ou
 * l'échelle d'une question Likert avec ses libellés. Sa réponse est mise en avant.
 */
function Offered({ row }: { row: PsyAnswerRow }) {
  if (row.status === 'unanswered') return null;
  const answered = row.status === 'answered';
  if (row.options && row.options.length > 0) {
    const chosen = answered ? chosenIds(row.value) : new Set<string>();
    const items = row.options.map((option) => ({
      key: option.id,
      text: option.label,
      chosen: chosen.has(option.id),
    }));
    return <OfferedList label={r.offered} items={items} />;
  }

  const scale = row.scale;
  if (!scale) return null;
  const value = answered && typeof row.value === 'number' ? row.value : null;
  const labels = scale.labels ?? [];
  if (labels.length !== scale.max - scale.min + 1) {
    if (value === null) return null;
    return (
      <span className="bog-sub">
        {r.scaleRange(formatNumber(value), formatNumber(scale.min), formatNumber(scale.max))}
      </span>
    );
  }
  const items = labels.map((text, index) => ({
    key: String(index),
    text,
    chosen: value === scale.min + index,
    position: scale.min + index,
  }));
  return <OfferedList label={r.scale} items={items} scale />;
}

function AnswerCell({ row }: { row: PsyAnswerRow }) {
  const value = row.value;
  const free = row.type === 'text' || (typeof value === 'object' && value !== null && 'text' in value);
  let content: ReactNode;
  // Une réponse donnée suffit à dire « répondu » ; sinon on affiche l'état.
  if (row.status !== 'answered') content = <span className="bog-state">{r.states[row.status]}</span>;
  else if (row.answer_label === null) content = row.hidden_by_youth ? null : <Missing />;
  else if (free) content = <span className="bog-quote">{quoted(row.answer_label)}</span>;
  else content = frenchSpacing(row.answer_label);

  return (
    <>
      {content}
      <Offered row={row} />
      {row.hidden_by_youth && <Flag tone="youth">{r.hidden}</Flag>}
    </>
  );
}

function ItemSource({
  source,
  number,
  anchor,
}: {
  source: ItemSourceRef | null;
  number: number | undefined;
  anchor: (id: string) => string;
}) {
  if (!source) return <p className="bog-item-source muted">{r.noSource}</p>;
  const title = source.source?.title ?? source.source_id;
  const details = [source.ref && r.itemRef(source.ref), source.relation && r.relations[source.relation]]
    .filter(Boolean)
    .join(', ');
  return (
    <div className="bog-item-source">
      <p>
        {number !== undefined && source.source && (
          <a className="bog-cite" href={`#${anchor(source.source.id)}`}>
            [{number}]<span className="visually-hidden"> {r.sourceRef(title)}</span>
          </a>
        )}
        <span>{title}</span>
        {details && <span className="bog-sub">{details}</span>}
      </p>
      {source.original && (
        <p className="bog-original">
          <span className="visually-hidden">{r.original} : </span>
          <span lang="en">{quoted(source.original)}</span>
        </p>
      )}
    </div>
  );
}

function ItemTable({
  data,
  instrument,
  title,
  cursors,
  numbers,
  anchor,
}: {
  data: PsyRunDetail;
  instrument: InstrumentView | null;
  title: string;
  cursors: Cursors;
  numbers: Map<string, number>;
  anchor: (id: string) => string;
}) {
  if (data.answers.length === 0) return <p className="empty">{r.noItems}</p>;
  const groups: { chapter: string | null; rows: PsyAnswerRow[] }[] = [];
  for (const row of data.answers) {
    const chapter = row.chapter ?? null;
    const last = groups.at(-1);
    if (last && last.chapter === chapter) last.rows.push(row);
    else groups.push({ chapter, rows: [row] });
  }

  return (
    <div className="table-wrap">
      <table className="table table--stack bog-table bog-items">
        <caption className="visually-hidden">{r.caption(title)}</caption>
        <colgroup>
          <col className="bog-col-position" />
          <col className="bog-col-question" />
          <col className="bog-col-answer" />
          <col className="bog-col-time" />
          <col className="bog-col-signals" />
          <col className="bog-col-source" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col" className="numeric">
              {r.position}
            </th>
            <th scope="col">{r.question}</th>
            <th scope="col">{r.answer}</th>
            <th scope="col" className="numeric">
              {r.time}
            </th>
            <th scope="col">{r.signals}</th>
            <th scope="col">{r.source}</th>
          </tr>
        </thead>
        {groups.map((group, index) => (
          <tbody key={`${group.chapter ?? 'sans-chapitre'}-${index}`}>
            {group.chapter && (
              <tr className="bog-chapter">
                <th scope="rowgroup" colSpan={6}>
                  {r.chapter(chapterTitle(instrument, group.chapter))}
                </th>
              </tr>
            )}
            {group.rows.map((row) => (
              <tr key={row.item_id} className={row.status === 'answered' ? undefined : 'bog-row--muted'}>
                <td className="numeric">{row.position}</td>
                <th scope="row" className="bog-prompt">
                  {frenchSpacing(row.prompt)}
                </th>
                <td>
                  <AnswerCell row={row} />
                </td>
                <td className="numeric">
                  {row.response_ms !== null ? formatDuration(row.response_ms) : <Missing />}
                </td>
                <td>
                  <SignalList signals={row.signals} cursors={cursors} tier={instrument?.tier} />
                </td>
                <td>
                  <ItemSource
                    source={row.source}
                    number={row.source?.source ? numbers.get(row.source.source.id) : undefined}
                    anchor={anchor}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}

function trialOutcome(value: unknown): 'ok' | 'ko' | 'na' {
  if (!value || typeof value !== 'object') return 'na';
  const correct = (value as Record<string, unknown>).correct;
  if (correct === true) return 'ok';
  return correct === false ? 'ko' : 'na';
}

function PerformanceDetail({ data, title, cursors }: { data: PsyRunDetail; title: string; cursors: Cursors }) {
  const metrics = performanceMetrics(data.run.metrics);
  return (
    <>
      {metrics.length > 0 && (
        <div className="bog-detail__block">
          <h4>{r.metrics}</h4>
          <MetricList metrics={metrics} />
        </div>
      )}
      {data.run_signals.length > 0 && (
        <div className="bog-detail__block">
          <h4>{r.runSignals}</h4>
          <SignalList signals={data.run_signals} cursors={cursors} />
        </div>
      )}
      {data.answers.length === 0 ? (
        <p className="empty">{r.noTrials}</p>
      ) : (
        <div className="table-wrap">
          <table className="table table--stack bog-table bog-trials">
            <caption className="visually-hidden">{r.trialsCaption(title)}</caption>
            <colgroup>
              <col className="bog-col-position" />
              <col className="bog-col-trial" />
              <col className="bog-col-outcome" />
              <col className="bog-col-sequence" />
              <col className="bog-col-time" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col" className="numeric">
                  {r.position}
                </th>
                <th scope="col">{r.trial}</th>
                <th scope="col">{r.result}</th>
                <th scope="col">{r.trialDetail}</th>
                <th scope="col" className="numeric">
                  {r.time}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.answers.map((row) => (
                <tr key={row.item_id}>
                  <td className="numeric">{row.position}</td>
                  <th scope="row">{frenchSpacing(row.prompt)}</th>
                  <td>
                    <span className={`bog-trial bog-trial--${trialOutcome(row.value)}`}>
                      {row.answer_label ?? <Missing />}
                    </span>
                  </td>
                  <td className="bog-sequence">{trialDetail(row.value) ?? <Missing />}</td>
                  <td className="numeric">
                    {row.response_ms !== null ? formatDuration(row.response_ms) : <Missing />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function RunDetail({
  run,
  detail,
  cursors,
  onRetry,
}: {
  run: PsyRun;
  detail: Detail<PsyRunDetail>;
  cursors: Cursors;
  onRetry: () => void;
}) {
  const { weights } = useMethod();
  if (detail.state === 'loading') return <Loading />;
  if (detail.state === 'error') return <ErrorState message={detail.message} onRetry={onRetry} />;

  const data = detail.data;
  const instrument: InstrumentView | null = data.instrument ?? run.instrument;
  const performance = instrument?.kind === 'performance';
  const title = instrument?.title ?? run.instrument_id;
  const times = data.answers.flatMap((row) =>
    row.status === 'answered' && row.response_ms !== null ? [row.response_ms] : [],
  );
  const medianTime = median(times);
  let counting: string = performance ? r.countsGame : r.countsDone;
  if (instrument?.kind === 'quiz') counting = r.countsNow;
  else if (data.run.status !== 'completed') counting = r.countsAtEnd;

  // Numérotation des sources : celles de l'instrument d'abord, puis celles des items.
  const cited: GameSource[] = [];
  const numbers = new Map<string, number>();
  const cite = (source: GameSource | null | undefined) => {
    if (source && !numbers.has(source.id)) {
      cited.push(source);
      numbers.set(source.id, cited.length);
    }
  };
  instrument?.sources.forEach(cite);
  data.answers.forEach((row) => cite(row.source?.source));
  const anchor = (sourceId: string) => `${runAnchor(run.id)}-source-${sourceId}`;

  return (
    <div className="bog-detail">
      <dl className="bog-meta">
        {instrument && (
          <div>
            <dt>{r.tier}</dt>
            <dd>
              <TierChip tier={instrument.tier} label={instrument.tier_label} />{' '}
              {r.tierWeight(formatNumber(tierWeight(instrument.tier, weights)))}
            </dd>
          </div>
        )}
        {instrument?.scoring_note && (
          <div>
            <dt>{r.scoring}</dt>
            <dd>{instrument.scoring_note}</dd>
          </div>
        )}
        {medianTime !== null && (
          <div>
            <dt>{r.median}</dt>
            <dd>{formatDuration(medianTime)}</dd>
          </div>
        )}
        <div>
          <dt>{r.counting}</dt>
          <dd>{counting}</dd>
        </div>
      </dl>
      {performance ? (
        <PerformanceDetail data={data} title={title} cursors={cursors} />
      ) : (
        <ItemTable
          data={data}
          instrument={instrument}
          title={title}
          cursors={cursors}
          numbers={numbers}
          anchor={anchor}
        />
      )}
      {cited.length > 0 && (
        <section className="bog-cited" aria-labelledby={`bog-run-${run.id}-sources`}>
          <h4 id={`bog-run-${run.id}-sources`}>{r.sources}</h4>
          <ol>
            {cited.map((source) => (
              <li key={source.id} id={anchor(source.id)}>
                <p className="bog-strong">{source.title}</p>
                <SourceDetails source={source} />
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}

function RunRow({
  run,
  detail,
  onLoad,
  cursors,
}: {
  run: PsyRun;
  detail: Detail<PsyRunDetail> | undefined;
  onLoad: (id: string) => Promise<boolean>;
  cursors: Cursors;
}) {
  const [open, setOpen] = useState(false);
  const instrument = run.instrument;
  const performance = instrument?.kind === 'performance';
  const title = instrument?.title ?? run.instrument_id;
  const status = runStatus(run);
  const skipped = run.seen - run.answered;
  const detailId = `${runAnchor(run.id)}-detail`;

  function toggle() {
    if (!open) void onLoad(run.id);
    setOpen(!open);
  }

  return (
    <>
      <tr id={runAnchor(run.id)}>
        <th scope="row">
          <span className="bog-name">{title}</span>
          <span className="bog-run-kind">
            {instrument ? bo.kinds[instrument.kind] : t.unknownInstrument}
            {instrument && <TierChip tier={instrument.tier} label={instrument.tier_label} />}
          </span>
          <button
            type="button"
            className="bog-toggle"
            aria-expanded={open}
            aria-controls={detailId}
            onClick={toggle}
          >
            {open ? t.hide : performance ? t.showTrials : t.showAnswers}
            <span className="visually-hidden"> : {title}</span>
            <Chevron />
          </button>
        </th>
        <td>
          <span className={status === 'completed' ? 'status status--on' : 'status'}>{t.states[status]}</span>
        </td>
        <td className="bog-dates">
          <span>{t.started(formatDateTime(run.started_at))}</span>
          {run.completed_at && <span>{t.completed(formatDateTime(run.completed_at))}</span>}
          {!run.completed_at && run.paused_at && <span>{t.paused(formatDateTime(run.paused_at))}</span>}
        </td>
        <td className="bog-count">
          {performance ? t.trials(run.answered) : t.answered(run.answered, run.total)}
          {!performance && skipped > 0 && <span className="bog-sub">{t.skipped(skipped)}</span>}
        </td>
        <td>
          <RunScores run={run} cursors={cursors} />
        </td>
      </tr>
      <tr id={detailId} className="bog-detail-row" hidden={!open} data-loaded={detail ? '' : undefined}>
        <td colSpan={5}>
          {detail && (
            <RunDetail run={run} detail={detail} cursors={cursors} onRetry={() => void onLoad(run.id)} />
          )}
        </td>
      </tr>
    </>
  );
}

export function RunSection({
  runs,
  details,
  cursors,
}: {
  runs: PsyRun[];
  details: Details<PsyRunDetail>;
  cursors: Cursors;
}) {
  return (
    <section className="bog-section" aria-labelledby="bog-runs-title">
      <h3 id="bog-runs-title">{t.title}</h3>
      {runs.length === 0 ? (
        <p className="empty">{t.empty}</p>
      ) : (
        <div className="table-wrap">
          <table className="table table--stack bog-table bog-runs">
            <caption className="visually-hidden">{t.title}</caption>
            <colgroup>
              <col className="bog-col-game" />
              <col className="bog-col-status" />
              <col className="bog-col-dates" />
              <col className="bog-col-answers" />
              <col className="bog-col-scores" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{t.game}</th>
                <th scope="col">{t.status}</th>
                <th scope="col">{t.dates}</th>
                <th scope="col">{t.answers}</th>
                <th scope="col">{t.scores}</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <RunRow
                  key={run.id}
                  run={run}
                  detail={details.details[run.id]}
                  onLoad={details.load}
                  cursors={cursors}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
