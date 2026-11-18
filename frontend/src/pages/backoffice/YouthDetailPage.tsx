import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { Conversation, Message, YouthDetail } from '../../api/types';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { formatDateTime } from '../../components/format';
import { fr } from '../../content/fr';

const t = fr.backoffice;

function ConversationItem({
  youthId,
  conversation,
  shared,
}: {
  youthId: string;
  conversation: Conversation;
  shared: boolean;
}) {
  const [messages, setMessages] = useState<Message[] | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function toggle() {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setError(null);
    try {
      const detail = await api.getYouthConversation(youthId, conversation.id);
      setMessages(detail.messages);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  return (
    <li className="card stack-sm">
      <div className="card__head">
        <span>
          {t.conversationLabel(formatDateTime(conversation.last_message_at), conversation.message_count)}
        </span>
        {shared && (
          <button type="button" className="button button--small" onClick={() => void toggle()} aria-expanded={open}>
            {open ? t.hide : t.read}
          </button>
        )}
      </div>
      {open && error && <ErrorState message={error} />}
      {open && !error && !messages && <Loading />}
      {open && messages && (
        <div className="transcript">
          {messages.map((message) => (
            <p key={message.id} className={`transcript__line transcript__line--${message.role}`}>
              <strong>{message.role === 'user' ? t.youth : t.companion}</strong>
              {message.content}
            </p>
          ))}
        </div>
      )}
    </li>
  );
}

export function YouthDetailPage() {
  const { youthId = '' } = useParams();
  const [detail, setDetail] = useState<YouthDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setError(null);
      try {
        setDetail(await api.getYouth(youthId, signal));
      } catch (caught) {
        if (!signal?.aborted) setError(errorMessage(caught));
      }
    },
    [youthId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error) return <ErrorState message={error} onRetry={() => void load()} />;
  if (!detail) return <Loading />;

  const { youth, skills, pending_skills: pending, conversations } = detail;

  return (
    <div className="stack">
      <header className="stack-sm">
        <Link to="/psy/jeunes" className="back-link">
          ← {t.back}
        </Link>
        <h1>{youth.display_name}</h1>
      </header>

      <div className="detail-grid">
        <section className="stack-sm">
          <h2>
            {t.skillsTitle} <span className="count">{skills.length}</span>
          </h2>
          {pending > 0 && <p className="muted">{t.pendingNote(pending)}</p>}
          {skills.length === 0 ? (
            <p className="empty">{t.noSkills}</p>
          ) : (
            <ul className="stack-sm plain-list">
              {skills.map((skill) => (
                <li key={skill.id} className="card stack-sm">
                  <div className="card__head">
                    <h3>{skill.name}</h3>
                    <span className="chip">
                      {fr.skills.categories[skill.category] ?? skill.category}
                    </span>
                  </div>
                  {skill.description && <p>{skill.description}</p>}
                  <blockquote className="quote">
                    <span className="quote__label">{t.quote}</span>« {skill.quote} »
                  </blockquote>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="stack-sm">
          <h2>
            {t.conversationsTitle} <span className="count">{conversations.length}</span>
          </h2>
          {!youth.share_transcripts && <p className="notice">{t.locked}</p>}
          {conversations.length === 0 ? (
            <p className="empty">{t.noConversations}</p>
          ) : (
            <ul className="stack-sm plain-list">
              {conversations.map((conversation) => (
                <ConversationItem
                  key={conversation.id}
                  youthId={youth.id}
                  conversation={conversation}
                  shared={youth.share_transcripts}
                />
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
