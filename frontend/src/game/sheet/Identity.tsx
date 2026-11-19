import { useEffect, useId, useRef, useState, type CSSProperties, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../../components/Feedback';
import type { GameFact } from '../types';
import { isColorFact, swatchFor } from './colors';
import { orderFacts } from './facts';
import { ActionIcon } from './glyphs';
import { SheetBox } from './SheetBox';
import { sheetFr } from './sheet.fr';

const t = sheetFr.identity;
const MAX_LENGTH = 120;
/** Sur téléphone, les premiers détails seulement, pour garder les talents près du haut (voir sheet.css). */
const COLLAPSED = 6;

export type FactChanges = { value?: string; hidden?: boolean };

interface Props {
  facts: GameFact[];
  /** Lien vers le quiz quand la fiche n'a encore aucun détail. */
  quizLink: string | null;
  onChange: (key: string, changes: FactChanges) => Promise<GameFact>;
  announce: (message: string) => void;
}

function FactValue({ fact }: { fact: GameFact }) {
  const color = isColorFact(fact) ? swatchFor(fact.value) : null;
  return (
    <span className="sheet-fact__value">
      {color && (
        <span
          className="sheet-swatch"
          style={{ '--swatch': color } as CSSProperties}
          aria-hidden="true"
        />
      )}
      <span className="sheet-fact__text">{fact.value}</span>
      {fact.edited && (
        <span className="sheet-edited">
          <ActionIcon name="pencil" />
          {t.edited}
        </span>
      )}
    </span>
  );
}

function FactEditor({
  fact,
  labelId,
  onSave,
  onHide,
  onCancel,
}: {
  fact: GameFact;
  labelId: string;
  onSave: (value: string) => Promise<void>;
  onHide: () => Promise<void>;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(fact.value);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorId = useId();
  const hintId = useId();
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
    input.current?.select();
  }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(errorMessage(caught));
      setBusy(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const clean = value.trim();
    if (!clean || clean.length > MAX_LENGTH) {
      setError(t.invalid);
      return;
    }
    if (clean === fact.value) {
      onCancel();
      return;
    }
    void run(() => onSave(clean));
  }

  return (
    <form
      className="sheet-fact__form"
      noValidate
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          onCancel();
        }
      }}
    >
      <input
        ref={input}
        className="sheet-input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        maxLength={MAX_LENGTH}
        required
        autoComplete="off"
        aria-labelledby={labelId}
        aria-describedby={error ? errorId : undefined}
        aria-invalid={error ? true : undefined}
      />
      {error && (
        <p id={errorId} className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="sheet-fact__actions">
        <button type="submit" className="button button--primary button--small" disabled={busy}>
          {t.save}
        </button>
        <button type="button" className="link-button" onClick={onCancel} disabled={busy}>
          {t.cancel}
        </button>
      </div>
      <div className="sheet-fact__hide">
        <button
          type="button"
          className="sheet-text-button"
          onClick={() => void run(onHide)}
          disabled={busy}
          aria-describedby={hintId}
        >
          <ActionIcon name="hide" />
          {t.hide}
        </button>
        <small id={hintId}>{t.hideHint}</small>
      </div>
    </form>
  );
}

/** Détails donnés au quiz : couleur préférée, passion… modifiables et masquables par le jeune. */
export function Identity({ facts, quizLink, onChange, announce }: Props) {
  const [editing, setEditing] = useState<string | null>(null);
  const editButtons = useRef(new Map<string, HTMLButtonElement>());
  const hiddenSummary = useRef<HTMLElement>(null);
  const [focusAfter, setFocusAfter] = useState<{ key: string } | 'hidden' | null>(null);
  const [showError, setShowError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const baseId = useId();
  const ordered = orderFacts(facts);
  const visible = ordered.filter((fact) => !fact.hidden);
  const hidden = ordered.filter((fact) => fact.hidden);

  useEffect(() => {
    if (!focusAfter) return;
    if (focusAfter === 'hidden') hiddenSummary.current?.focus();
    else editButtons.current.get(focusAfter.key)?.focus();
    setFocusAfter(null);
  }, [focusAfter]);

  function close(key: string) {
    setEditing(null);
    setFocusAfter({ key });
  }

  async function save(fact: GameFact, value: string) {
    await onChange(fact.key, { value });
    announce(t.saved(fact.label));
    close(fact.key);
  }

  async function hide(fact: GameFact) {
    await onChange(fact.key, { hidden: true });
    announce(t.hidden(fact.label));
    setEditing(null);
    setFocusAfter('hidden');
  }

  async function show(fact: GameFact) {
    setShowError(null);
    try {
      await onChange(fact.key, { hidden: false });
      announce(t.shown(fact.label));
      setFocusAfter({ key: fact.key });
    } catch (caught) {
      setShowError(errorMessage(caught));
    }
  }

  return (
    <SheetBox
      id="sheet-identity"
      title={t.title}
      intro={facts.length ? t.intro : undefined}
      className="sheet-area--identity"
    >
      {facts.length === 0 && (
        <p className="sheet-empty">
          {t.empty}
          {quizLink && (
            <>
              {' '}
              <Link to={quizLink} className="sheet-link">
                {t.emptyCta}
              </Link>
            </>
          )}
        </p>
      )}

      {visible.length > 0 && (
        <dl id={`${baseId}-facts`} className={`sheet-facts${expanded ? ' is-open' : ''}`}>
          {visible.map((fact) => {
            const labelId = `${baseId}-${fact.key}`;
            const isEditing = editing === fact.key;
            return (
              <div key={fact.key} className={`sheet-fact${isEditing ? ' is-editing' : ''}`}>
                <dt id={labelId} className="sheet-fact__label">
                  {fact.label}
                </dt>
                <dd className="sheet-fact__body">
                  {isEditing ? (
                    <FactEditor
                      fact={fact}
                      labelId={labelId}
                      onSave={(value) => save(fact, value)}
                      onHide={() => hide(fact)}
                      onCancel={() => close(fact.key)}
                    />
                  ) : (
                    <>
                      <FactValue fact={fact} />
                      <button
                        type="button"
                        className="sheet-icon-button"
                        aria-label={t.edit(fact.label)}
                        title={t.edit(fact.label)}
                        onClick={() => setEditing(fact.key)}
                        ref={(node) => {
                          if (node) editButtons.current.set(fact.key, node);
                          else editButtons.current.delete(fact.key);
                        }}
                      >
                        <ActionIcon name="pencil" />
                      </button>
                    </>
                  )}
                </dd>
              </div>
            );
          })}
        </dl>
      )}

      {visible.length > COLLAPSED && (
        <button
          type="button"
          className="sheet-text-button sheet-facts__more"
          aria-expanded={expanded}
          aria-controls={`${baseId}-facts`}
          onClick={() => setExpanded((open) => !open)}
        >
          {expanded ? t.less : t.more(visible.length - COLLAPSED)}
        </button>
      )}

      {hidden.length > 0 && (
        <details className="sheet-hidden">
          <summary ref={hiddenSummary}>
            <ActionIcon name="hide" />
            {t.hiddenSummary(hidden.length)}
          </summary>
          <ul className="sheet-hidden__list">
            {hidden.map((fact) => (
              <li key={fact.key}>
                <span>
                  <span className="sheet-fact__label">{fact.label}</span>
                  <span className="sheet-hidden__value">{fact.value}</span>
                </span>
                <button type="button" className="sheet-text-button" onClick={() => void show(fact)}>
                  <ActionIcon name="show" />
                  {t.show}
                </button>
              </li>
            ))}
          </ul>
          {showError && (
            <p className="form-error" role="alert">
              {showError}
            </p>
          )}
        </details>
      )}
    </SheetBox>
  );
}
