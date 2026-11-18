import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type { Skill, SkillStatus } from '../../api/types';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { fr } from '../../content/fr';
import { useYouthContext } from '../../layouts/YouthLayout';

const POLL_MS = 2500;
const t = fr.skills;

function SkillCard({
  skill,
  onChange,
}: {
  skill: Skill;
  onChange: (id: string, changes: { status?: SkillStatus; name?: string }) => Promise<void>;
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(skill.name);
  const [busy, setBusy] = useState(false);

  async function apply(changes: { status?: SkillStatus; name?: string }) {
    setBusy(true);
    try {
      await onChange(skill.id, changes);
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
        <div className="card__head">
          <h3>{skill.name}</h3>
          <span className="chip">{t.categories[skill.category] ?? skill.category}</span>
        </div>
      )}
      {skill.description && <p>{skill.description}</p>}
      <blockquote className="quote">
        <span className="quote__label">{t.youSaid}</span>« {skill.quote} »
      </blockquote>
      <div className="actions">
        {skill.status !== 'validated' && (
          <button
            type="button"
            className="button button--small button--primary"
            disabled={busy}
            onClick={() => void apply({ status: 'validated' })}
          >
            {skill.status === 'rejected' ? t.restore : t.validate}
          </button>
        )}
        {skill.status !== 'rejected' && (
          <button
            type="button"
            className="button button--small"
            disabled={busy}
            onClick={() => void apply({ status: 'rejected' })}
          >
            {skill.status === 'validated' ? t.withdraw : t.reject}
          </button>
        )}
        {!renaming && skill.status !== 'rejected' && (
          <button type="button" className="link-button" onClick={() => setRenaming(true)}>
            {t.rename}
          </button>
        )}
      </div>
    </li>
  );
}

export function SkillsPage() {
  const { setPendingSkills } = useYouthContext();
  const [skills, setSkills] = useState<Skill[] | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [sharing, setSharing] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const publish = useCallback(
    (next: Skill[]) => {
      setSkills(next);
      setPendingSkills(next.filter((skill) => skill.status === 'pending').length);
    },
    [setPendingSkills],
  );

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setError(null);
      try {
        const [refresh, privacy] = await Promise.all([api.refreshSkills(), api.getPrivacy(signal)]);
        const list = await api.listSkills(signal);
        publish(list.skills);
        setSharing(privacy.share_transcripts);
        setExtracting(refresh.extracting || list.extracting);
      } catch (caught) {
        if (!signal?.aborted) setError(errorMessage(caught));
      }
    },
    [publish],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (!extracting) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      api
        .listSkills(controller.signal)
        .then((list) => {
          publish(list.skills);
          setExtracting(list.extracting);
        })
        .catch(() => setExtracting(false));
    }, POLL_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [extracting, skills, publish]);

  async function change(id: string, changes: { status?: SkillStatus; name?: string }) {
    setActionError(null);
    try {
      const { skill } = await api.updateSkill(id, changes);
      publish((skills ?? []).map((item) => (item.id === id ? skill : item)));
    } catch (caught) {
      setActionError(errorMessage(caught));
      throw caught;
    }
  }

  async function toggleSharing(value: boolean) {
    setActionError(null);
    setSharing(value);
    try {
      setSharing((await api.updatePrivacy(value)).share_transcripts);
    } catch (caught) {
      setSharing(!value);
      setActionError(errorMessage(caught));
    }
  }

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!skills) return <Loading />;

  const byStatus = (status: SkillStatus) => skills.filter((skill) => skill.status === status);
  const pending = byStatus('pending');
  const validated = byStatus('validated');
  const rejected = byStatus('rejected');
  const safeChange = (id: string, changes: { status?: SkillStatus; name?: string }) =>
    change(id, changes).catch(() => undefined);

  return (
    <div className="scroll-area">
      <div className="page stack">
        <header className="stack-sm">
          <h1>{t.title}</h1>
          <p className="muted">{t.intro}</p>
        </header>

        {actionError && (
          <p className="form-error" role="alert">
            {actionError}
          </p>
        )}
        {extracting && (
          <p className="notice" role="status">
            {t.analysing}
          </p>
        )}
        {skills.length === 0 && !extracting && <p className="empty">{t.empty}</p>}

        {pending.length > 0 && (
          <section className="stack-sm">
            <h2>
              {t.pendingTitle} <span className="count">{pending.length}</span>
            </h2>
            <ul className="stack-sm plain-list">
              {pending.map((skill) => (
                <SkillCard key={skill.id} skill={skill} onChange={safeChange} />
              ))}
            </ul>
          </section>
        )}

        {validated.length > 0 && (
          <section className="stack-sm">
            <h2>
              {t.validatedTitle} <span className="count">{validated.length}</span>
            </h2>
            <p className="muted">{t.validatedHint}</p>
            <ul className="stack-sm plain-list">
              {validated.map((skill) => (
                <SkillCard key={skill.id} skill={skill} onChange={safeChange} />
              ))}
            </ul>
          </section>
        )}

        {rejected.length > 0 && (
          <details className="stack-sm">
            <summary>
              {t.rejectedTitle} <span className="count">{rejected.length}</span>
            </summary>
            <ul className="stack-sm plain-list">
              {rejected.map((skill) => (
                <SkillCard key={skill.id} skill={skill} onChange={safeChange} />
              ))}
            </ul>
          </details>
        )}

        {sharing !== null && (
          <label className="toggle card">
            <input
              type="checkbox"
              checked={sharing}
              onChange={(event) => void toggleSharing(event.target.checked)}
            />
            <span>
              <strong>{t.shareTitle}</strong>
              <small className="muted">{t.shareHint}</small>
            </span>
          </label>
        )}
      </div>
    </div>
  );
}
