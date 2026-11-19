import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type { Skill, SkillStatus } from '../../api/types';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { formatDay } from '../../components/format';
import { Highlight } from '../../components/Highlight';
import { CheckIcon, CrossIcon, PinIcon, TalentStar } from '../../components/Icons';
import { TalentRoute } from '../../components/TalentRoute';
import { fr } from '../../content/fr';
import { useTalents, type TalentChanges } from './useTalents';

const t = fr.map;

/** Retrouve les messages d'origine pour montrer chaque extrait dans son contexte. */
function useSourceMessages(talents: Skill[] | null) {
  const [messages, setMessages] = useState<Record<string, string>>({});
  const requested = useRef(new Set<string>());

  useEffect(() => {
    const counts = new Map<string, number>();
    for (const { conversation_id: id } of talents ?? []) {
      if (id) counts.set(id, (counts.get(id) ?? 0) + 1);
    }
    for (const [conversationId, count] of counts) {
      const key = `${conversationId}:${count}`;
      if (requested.current.has(key)) continue;
      requested.current.add(key);
      api
        .getConversation(conversationId)
        .then((detail) =>
          setMessages((current) => ({
            ...current,
            ...Object.fromEntries(detail.messages.map((m) => [m.id, m.content])),
          })),
        )
        .catch(() => requested.current.delete(key));
    }
  }, [talents]);

  return messages;
}

function TalentMark({ status }: { status: SkillStatus }) {
  if (status === 'pending') return <TalentStar />;
  return (
    <span className={`talent-card__mark${status === 'rejected' ? ' talent-card__mark--rejected' : ''}`}>
      {status === 'validated' ? <CheckIcon /> : <CrossIcon />}
    </span>
  );
}

function TalentCard({
  talent,
  source,
  onChange,
}: {
  talent: Skill;
  source?: string;
  onChange: (id: string, changes: TalentChanges) => Promise<void>;
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(talent.name);
  const [busy, setBusy] = useState(false);

  async function apply(changes: TalentChanges) {
    setBusy(true);
    try {
      await onChange(talent.id, changes);
      setRenaming(false);
    } finally {
      setBusy(false);
    }
  }

  function submitName(event: FormEvent) {
    event.preventDefault();
    void apply({ name });
  }

  return (
    <li className="card stack-sm">
      {renaming ? (
        <form className="rename" onSubmit={submitName}>
          <label className="field">
            <span>{t.nameLabel}</span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              minLength={3}
              maxLength={80}
              required
              autoFocus
            />
          </label>
          <div className="actions">
            <button type="submit" className="button button--small" disabled={busy}>
              {fr.common.save}
            </button>
            <button type="button" className="link-button" onClick={() => setRenaming(false)}>
              {fr.common.cancel}
            </button>
          </div>
        </form>
      ) : (
        <div className="talent-card__top">
          <TalentMark status={talent.status} />
          <div>
            <h2>{talent.name}</h2>
            <small className="talent-card__category">
              {t.categories[talent.category] ?? talent.category}
            </small>
          </div>
        </div>
      )}
      {talent.description && <p className="talent-card__description">{talent.description}</p>}
      {talent.origin === 'youth' ? (
        <span className="extract__source">
          <PinIcon />
          {t.addedByYou(formatDay(talent.created_at))}
        </span>
      ) : (
        <div className="extract">
          <span className="extract__source">
            <PinIcon />
            {t.source(formatDay(talent.created_at))}
          </span>
          <span>
            <Highlight text={source ?? talent.quote} quote={talent.quote} />
          </span>
        </div>
      )}
      <div className="actions">
        {talent.status === 'pending' && (
          <button
            type="button"
            className="button button--small button--keep"
            disabled={busy}
            onClick={() => void apply({ status: 'validated' })}
          >
            {fr.found.keep}
          </button>
        )}
        {talent.status === 'rejected' && (
          <button
            type="button"
            className="button button--small button--keep"
            disabled={busy}
            onClick={() => void apply({ status: 'validated' })}
          >
            {t.restore}
          </button>
        )}
        {talent.status !== 'rejected' && (
          <button
            type="button"
            className="button button--small"
            disabled={busy}
            onClick={() => void apply({ status: 'rejected' })}
          >
            {talent.status === 'validated' ? t.withdraw : fr.found.reject}
          </button>
        )}
        {!renaming && talent.status !== 'rejected' && (
          <button
            type="button"
            className="button button--small"
            disabled={busy}
            onClick={() => setRenaming(true)}
          >
            {t.rephrase}
          </button>
        )}
      </div>
    </li>
  );
}

export function MapPage() {
  const { talents, extracting, error, retry, update, add } = useTalents({ analyseOnOpen: true });
  const [actionError, setActionError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const [newStory, setNewStory] = useState('');
  const [saving, setSaving] = useState(false);

  async function submitNew(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setActionError(null);
    try {
      await add(newName, newStory);
      setAdding(false);
      setNewName('');
      setNewStory('');
      setChosenTab('validated');
    } catch (caught) {
      setActionError(errorMessage(caught));
    } finally {
      setSaving(false);
    }
  }
  const sources = useSourceMessages(talents);
  const [chosenTab, setChosenTab] = useState<SkillStatus | null>(null);

  async function change(id: string, changes: TalentChanges) {
    setActionError(null);
    try {
      await update(id, changes);
    } catch (caught) {
      setActionError(errorMessage(caught));
      throw caught;
    }
  }
  const safeChange = (id: string, changes: TalentChanges) =>
    change(id, changes).catch(() => undefined);

  if (error) return <ErrorState message={error} onRetry={() => void retry()} />;
  if (!talents) return <Loading />;

  const byStatus = (status: SkillStatus) => talents.filter((talent) => talent.status === status);
  const pending = byStatus('pending');
  const validated = byStatus('validated');
  const rejected = byStatus('rejected');
  const automaticTab: SkillStatus = pending.length || !validated.length ? 'pending' : 'validated';
  const activeTab = chosenTab ?? automaticTab;
  const visible = byStatus(activeTab);

  const tabs: { status: SkillStatus; count: number }[] = [
    { status: 'pending', count: pending.length },
    { status: 'validated', count: validated.length },
  ];
  if (rejected.length) tabs.push({ status: 'rejected', count: rejected.length });

  return (
    <div className="scroll-area">
      <div className="page stack-sm">
        <header className="page-head">
          <h1>{t.title}</h1>
          <p className="muted">{t.summary(pending.length, validated.length)}</p>
        </header>

        {adding ? (
          <form className="card stack-sm add-talent" onSubmit={submitNew}>
            <label className="field">
              <span>{t.addName}</span>
              <input
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                minLength={3}
                maxLength={80}
                required
                autoFocus
              />
            </label>
            <label className="field">
              <span>{t.addStory}</span>
              <input value={newStory} onChange={(event) => setNewStory(event.target.value)} maxLength={300} />
            </label>
            <div className="actions">
              <button type="submit" className="button button--small button--keep" disabled={saving}>
                {t.addSave}
              </button>
              <button type="button" className="link-button" onClick={() => setAdding(false)}>
                {fr.common.cancel}
              </button>
            </div>
          </form>
        ) : (
          <button type="button" className="button button--small add-talent__open" onClick={() => setAdding(true)}>
            + {t.addOpen}
          </button>
        )}

        <TalentRoute talents={talents} />

        <div className="tabs" role="group" aria-label={t.title}>
          {tabs.map(({ status, count }) => (
            <button
              key={status}
              type="button"
              aria-pressed={activeTab === status}
              onClick={() => setChosenTab(status)}
            >
              {t.tabs[status]} · {count}
            </button>
          ))}
        </div>

        {actionError && (
          <p className="form-error" role="alert">
            {actionError}
          </p>
        )}
        {extracting && (
          <p className="notice notice--talent" role="status">
            {t.analysing}
          </p>
        )}
        <p className="muted">{t.keptHint}</p>
        {visible.length === 0 && !extracting && <p className="empty">{t.empty[activeTab]}</p>}

        <ul className="stack-sm plain-list">
          {visible.map((talent) => (
            <TalentCard
              key={talent.id}
              talent={talent}
              source={talent.source_message_id ? sources[talent.source_message_id] : undefined}
              onChange={safeChange}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}
