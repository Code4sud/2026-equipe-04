import type { ReactNode } from 'react';
import { CheckIcon, CrossIcon } from '../../components/Icons';
import type { GameSource, PsyCursor, Verdict } from '../types';
import { bo } from './backoffice.fr';
import { describeValue, formatDay, tierLabel } from './format';

/** Cellule vide, lisible par un lecteur d'écran. */
export function Missing({ label = bo.missing }: { label?: string }) {
  return (
    <span className="bog-missing">
      <span aria-hidden="true">–</span>
      <span className="visually-hidden">{label}</span>
    </span>
  );
}

export function TierChip({ tier, label }: { tier: string; label?: string }) {
  return <span className={`bog-tier bog-tier--${tier}`}>{tierLabel(tier, label)}</span>;
}

export function VerdictBadge({ verdict }: { verdict: Verdict | null | undefined }) {
  if (verdict === 'disagree') {
    return (
      <span className="bog-verdict bog-verdict--disagree">
        <CrossIcon />
        {bo.verdict.disagree}
      </span>
    );
  }
  if (verdict === 'agree') {
    return (
      <span className="bog-verdict bog-verdict--agree">
        <CheckIcon />
        {bo.verdict.agree}
      </span>
    );
  }
  return <span className="bog-verdict bog-verdict--none">{bo.verdict.none}</span>;
}

/**
 * Avis du jeune sur un curseur : ce qu'il voyait quand il a répondu, et quand. Un avis donné
 * avant un changement de pôle reste affiché, au passé, pour qu'on puisse en parler avec lui.
 */
export function VerdictCell({ cursor }: { cursor: PsyCursor }) {
  const detail = cursor.verdict_detail;
  const verdict = detail?.verdict ?? cursor.verdict;
  if (!verdict) return <VerdictBadge verdict={null} />;
  const label = detail?.label_at_verdict ?? null;
  const date = detail?.at ? formatDay(detail.at) : null;

  if (detail?.stale) {
    const value = detail.value_at_verdict === null ? null : describeValue(cursor, detail.value_at_verdict);
    return (
      <>
        <span className="bog-verdict bog-verdict--stale">
          {verdict === 'agree' ? <CheckIcon /> : <CrossIcon />}
          {verdict === 'agree' ? bo.verdict.staleAgree : bo.verdict.staleDisagree}
        </span>
        <span className="bog-sub bog-verdict__detail">
          {bo.verdict.stale(bo.verdict.judged(label, value), date)}
        </span>
      </>
    );
  }

  const context = bo.verdict.on(label, date);
  return (
    <>
      <VerdictBadge verdict={verdict} />
      {context && <span className="bog-sub bog-verdict__detail">{context}</span>}
    </>
  );
}

export function Chevron() {
  return (
    <svg className="bog-chevron" viewBox="0 0 12 12" aria-hidden="true">
      <path
        d="M2.5 4.5L6 8l3.5-3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Flag({ children, tone = 'muted' }: { children: ReactNode; tone?: 'muted' | 'youth' }) {
  return <span className={`bog-flag bog-flag--${tone}`}>{children}</span>;
}

/** Référence complète d'une source : citation, lien, licence, validation, adaptation. */
export function SourceDetails({ source, extra }: { source: GameSource; extra?: ReactNode }) {
  const t = bo.sources.list;
  return (
    <>
      <p className="bog-citation">{source.citation}</p>
      <dl className="bog-source-meta">
        {source.url && (
          <div>
            <dt>{t.link}</dt>
            <dd>
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.url.replace(/^https?:\/\//, '').replace(/\/$/, '')}
              </a>
            </dd>
          </div>
        )}
        <div>
          <dt>{t.licence}</dt>
          <dd>{source.licence || <Missing />}</dd>
        </div>
        <div>
          <dt>{t.validated}</dt>
          <dd>{source.validated ? t.validatedYes : t.validatedNo}</dd>
        </div>
        <div>
          <dt>{t.adaptation}</dt>
          <dd>{source.adaptation || <Missing />}</dd>
        </div>
        {source.note && (
          <div>
            <dt>{t.note}</dt>
            <dd>{source.note}</dd>
          </div>
        )}
        {extra}
      </dl>
    </>
  );
}
