import { useCallback, useEffect, useState } from 'react';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import type { GameSource, InstrumentInfo, PsyArchetypeInfo, PsyCatalog } from '../types';
import { bo } from './backoffice.fr';
import './backoffice.css';
import { TIER_ORDER, formatNumber } from './format';
import { FALLBACK_METHOD, fetchPsyCatalog, methodFrom, type Method as MethodValues } from './method';
import { Missing, SourceDetails, TierChip } from './parts';

const t = bo.sources;

type Catalog = Pick<PsyCatalog, 'instruments' | 'sources'>;

const sourceAnchor = (id: string) => `source-${id}`;

/** Poids et seuils du serveur une fois le catalogue chargé, les copies de secours avant. */
function Method({ method }: { method: MethodValues }) {
  const { weights, thresholds } = method;
  return (
    <section className="bog-section bog-prose" aria-labelledby="bog-method">
      <h2 id="bog-method">{t.method.title}</h2>
      {t.method.paragraphs.map((text) => (
        <p key={text}>{text}</p>
      ))}
      <div className="table-wrap bog-weights">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{t.method.tier}</th>
              <th scope="col">{t.method.meaning}</th>
              <th scope="col" className="numeric">
                {t.method.weight}
              </th>
            </tr>
          </thead>
          <tbody>
            {TIER_ORDER.map((tier) => (
              <tr key={tier}>
                <th scope="row">
                  <TierChip tier={tier} />
                </th>
                <td>{bo.tierMeaning[tier]}</td>
                <td className="numeric">{formatNumber(weights[tier])}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {t.method.after(formatNumber(thresholds.medium), formatNumber(thresholds.high)).map((text) => (
        <p key={text}>{text}</p>
      ))}
    </section>
  );
}

/** Comment l'archétype montré au jeune est choisi, et la liste des archétypes une fois chargée. */
function Archetypes({ archetypes }: { archetypes: PsyArchetypeInfo[] | undefined }) {
  const a = t.archetypes;
  return (
    <section className="bog-section bog-prose" aria-labelledby="bog-archetypes">
      <h2 id="bog-archetypes">{a.title}</h2>
      {a.paragraphs.map((text) => (
        <p key={text}>{text}</p>
      ))}
      {archetypes && archetypes.length > 0 && (
        <div className="table-wrap bog-weights">
          <table className="table bog-archetypes">
            <caption className="visually-hidden">{a.caption}</caption>
            <thead>
              <tr>
                <th scope="col">{a.name}</th>
                <th scope="col">{a.cursor}</th>
                <th scope="col">{a.pole}</th>
                <th scope="col">{a.quality}</th>
              </tr>
            </thead>
            <tbody>
              {archetypes.map((archetype) => (
                <tr key={archetype.id}>
                  <th scope="row">
                    <span className="bog-archetype">
                      <span className="bog-archetype__emoji" aria-hidden="true">
                        {archetype.emoji}
                      </span>
                      {archetype.name}
                    </span>
                  </th>
                  {/* Espace insécable avant la flèche : jamais « ↔ » seul en début de ligne. */}
                  <td>{archetype.trait_label?.replace(' ↔ ', '\u00a0↔ ') ?? a.balancedCursor}</td>
                  <td>{archetype.pole_label}</td>
                  <td>{archetype.quality}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Limits() {
  return (
    <section className="bog-section bog-prose" aria-labelledby="bog-limits">
      <h2 id="bog-limits">{t.limits.title}</h2>
      <ul className="bog-limits">
        {t.limits.items.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
    </section>
  );
}

function Instruments({ instruments }: { instruments: InstrumentInfo[] }) {
  const s = t.instruments;
  return (
    <section className="bog-section" aria-labelledby="bog-instruments">
      <h2 id="bog-instruments">{s.title}</h2>
      {instruments.length === 0 ? (
        <p className="empty">{s.empty}</p>
      ) : (
        <div className="table-wrap">
          <table className="table table--stack bog-table bog-instruments">
            <colgroup>
              <col className="bog-col-instrument" />
              <col className="bog-col-tier" />
              <col className="bog-col-scoring" />
              <col className="bog-col-sources" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{s.instrument}</th>
                <th scope="col">{s.tier}</th>
                <th scope="col">{s.scoring}</th>
                <th scope="col">{s.sources}</th>
              </tr>
            </thead>
            <tbody>
              {instruments.map((instrument) => {
                const sources = instrument.sources.filter((source): source is GameSource => source !== null);
                return (
                  <tr key={instrument.id} id={`instrument-${instrument.id}`}>
                    <th scope="row">
                      <span className="bog-name">{instrument.title}</span>
                      <span className="table__ref">{bo.kinds[instrument.kind]}</span>
                    </th>
                    <td>
                      <TierChip tier={instrument.tier} label={instrument.tier_label} />
                    </td>
                    <td>{instrument.scoring_note ?? <span className="muted">{s.noScoring}</span>}</td>
                    <td>
                      {sources.length === 0 ? (
                        <span className="muted">{s.noSource}</span>
                      ) : (
                        <ul className="plain-list">
                          {sources.map((source) => (
                            <li key={source.id}>
                              <a href={`#${sourceAnchor(source.id)}`}>{source.title}</a>
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Sources({ sources, instruments }: Catalog) {
  const s = t.list;
  return (
    <section className="bog-section" aria-labelledby="bog-sources">
      <h2 id="bog-sources">{s.title}</h2>
      {sources.length === 0 ? (
        <p className="empty">{s.empty}</p>
      ) : (
        <ul className="plain-list bog-source-list">
          {sources.map((source) => {
            const users = instruments.filter((instrument) =>
              instrument.sources.some((item) => item?.id === source.id),
            );
            return (
              <li key={source.id} id={sourceAnchor(source.id)} className="bog-source-card">
                <h3>{source.title}</h3>
                <SourceDetails
                  source={source}
                  extra={
                    <div>
                      <dt>{s.usedBy}</dt>
                      <dd>
                        {users.length === 0 ? (
                          <Missing label={s.unused} />
                        ) : (
                          users.map((instrument, index) => (
                            <span key={instrument.id}>
                              {index > 0 && ', '}
                              <a href={`#instrument-${instrument.id}`}>{instrument.title}</a>
                            </span>
                          ))
                        )}
                      </dd>
                    </div>
                  }
                />
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** /psy/sources : instruments, sources et méthode de calcul, pour la psychologue. */
export default function SourcesPage() {
  const [catalog, setCatalog] = useState<PsyCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Renvoie de quoi ignorer la réponse si la page est quittée entre-temps. */
  const load = useCallback(() => {
    let active = true;
    setError(null);
    fetchPsyCatalog().then(
      (data) => {
        if (active) setCatalog(data);
      },
      (caught: unknown) => {
        if (active) setError(errorMessage(caught));
      },
    );
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => load(), [load]);

  return (
    <div className="stack bog-page">
      <header className="page-head">
        <h1>{t.title}</h1>
        <p className="muted bog-lead">{t.intro}</p>
      </header>
      <nav className="bog-toc" aria-label={t.toc}>
        <ul className="plain-list">
          <li>
            <a href="#bog-method">{t.method.title}</a>
          </li>
          <li>
            <a href="#bog-archetypes">{t.archetypes.title}</a>
          </li>
          <li>
            <a href="#bog-limits">{t.limits.title}</a>
          </li>
          <li>
            <a href="#bog-instruments">{t.instruments.title}</a>
          </li>
          <li>
            <a href="#bog-sources">{t.list.title}</a>
          </li>
        </ul>
      </nav>
      <Method method={catalog ? methodFrom(catalog) : FALLBACK_METHOD} />
      <Archetypes archetypes={catalog?.archetypes} />
      <Limits />
      {error ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : !catalog ? (
        <Loading />
      ) : (
        <>
          <Instruments instruments={catalog.instruments} />
          <Sources sources={catalog.sources} instruments={catalog.instruments} />
        </>
      )}
    </div>
  );
}
