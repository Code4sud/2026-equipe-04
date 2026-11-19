import { useState } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../components/Feedback';
import type { CharacterSheet, Verdict, YouthTrait } from '../types';
import { ActionIcon } from './glyphs';
import { SheetBox } from './SheetBox';
import { sheetFr, typo } from './sheet.fr';

const t = sheetFr.character;

type TraitGroup = CharacterSheet['trait_groups'][number];

interface Props {
  groups: TraitGroup[];
  /** Où aller pour remplir cette partie : le quiz, puis les jeux. */
  next: { to: string; text: string; cta: string } | null;
  onVerdict: (traitId: string, verdict: Verdict | null) => Promise<void>;
}

function subjectOf(trait: YouthTrait) {
  return trait.kind === 'bipolar'
    ? t.pair(typo(trait.low ?? ''), typo(trait.high ?? ''))
    : typo(trait.label ?? '');
}

function VerdictButtons({
  trait,
  onVerdict,
}: {
  trait: YouthTrait;
  onVerdict: Props['onVerdict'];
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function choose(verdict: Verdict) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      // Appuyer de nouveau sur le même bouton retire l'avis.
      await onVerdict(trait.id, trait.verdict === verdict ? null : verdict);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="sheet-verdict-wrap">
      <div className="sheet-verdict" role="group" aria-label={t.verdictFor(subjectOf(trait))} aria-busy={busy}>
        <button
          type="button"
          className="sheet-verdict__button sheet-verdict__button--yes"
          aria-pressed={trait.verdict === 'agree'}
          onClick={() => void choose('agree')}
        >
          <ActionIcon name="check" />
          {t.yes}
        </button>
        <button
          type="button"
          className="sheet-verdict__button sheet-verdict__button--no"
          aria-pressed={trait.verdict === 'disagree'}
          onClick={() => void choose('disagree')}
        >
          <ActionIcon name="cross" />
          {t.no}
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/** Curseur neutre entre deux pôles : aucun côté n'est meilleur que l'autre. */
function BipolarTrait({ trait, onVerdict }: { trait: YouthTrait; onVerdict: Props['onVerdict'] }) {
  const low = typo(trait.low ?? '');
  const high = typo(trait.high ?? '');
  const label = trait.label ? typo(trait.label) : null;
  const lean = label === high ? 'high' : label === low ? 'low' : 'middle';
  const position = Math.min(97, Math.max(3, trait.value ?? 50));

  return (
    <li className={`sheet-trait sheet-trait--scale${trait.verdict ? ` is-${trait.verdict}` : ''}`}>
      <div className="sheet-scale" aria-hidden="true">
        <span className={`sheet-scale__end${lean === 'low' ? ' is-lean' : ''}`}>{low}</span>
        <span className={`sheet-scale__end sheet-scale__end--high${lean === 'high' ? ' is-lean' : ''}`}>
          {high}
        </span>
        <span className="sheet-scale__track">
          <span className="sheet-scale__mark" style={{ left: `${position}%` }} />
        </span>
      </div>
      <p className="visually-hidden">{t.leaning(low, high, label)}</p>
      <VerdictButtons trait={trait} onVerdict={onVerdict} />
    </li>
  );
}

function StrengthTrait({ trait, onVerdict }: { trait: YouthTrait; onVerdict: Props['onVerdict'] }) {
  return (
    <li className={`sheet-trait sheet-trait--strength${trait.verdict ? ` is-${trait.verdict}` : ''}`}>
      <span className="sheet-trait__label">{typo(trait.label ?? '')}</span>
      <VerdictButtons trait={trait} onVerdict={onVerdict} />
    </li>
  );
}

/** Caractère (curseurs bipolaires), ce qui attire et points forts (seulement les forces). */
export function Character({ groups, next, onVerdict }: Props) {
  const empty = groups.every((group) => group.traits.length === 0);

  return (
    <SheetBox
      id="sheet-character"
      title={t.title}
      intro={empty ? undefined : t.intro}
      className="sheet-area--character"
    >
      {empty ? (
        <p className="sheet-empty">
          {next?.text ?? t.empty}
          {next && (
            <>
              {' '}
              <Link to={next.to} className="sheet-link">
                {next.cta}
              </Link>
            </>
          )}
        </p>
      ) : (
        <div className="sheet-character">
          {groups.map((group) => {
            const scale = group.traits.some((trait) => trait.kind === 'bipolar');
            const headingId = `sheet-group-${group.id}`;
            return (
              <section
                key={group.id}
                className={`sheet-group${scale ? ' sheet-group--scale' : ''}`}
                aria-labelledby={headingId}
              >
                <h4 id={headingId} className="sheet-group__title">
                  {typo(group.label)}
                </h4>
                {group.traits.length === 0 ? (
                  <p className="sheet-group__empty">{t.noStrength}</p>
                ) : scale ? (
                  <ul className="sheet-traits">
                    {group.traits.map((trait) => (
                      <BipolarTrait key={trait.id} trait={trait} onVerdict={onVerdict} />
                    ))}
                  </ul>
                ) : (
                  <ol className="sheet-traits">
                    {group.traits.map((trait) => (
                      <StrengthTrait key={trait.id} trait={trait} onVerdict={onVerdict} />
                    ))}
                  </ol>
                )}
              </section>
            );
          })}
        </div>
      )}
    </SheetBox>
  );
}
