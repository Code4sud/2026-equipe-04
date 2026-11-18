import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api/client';
import type { Conversation, Message, Skill, YouthDetail } from '../../api/types';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { formatDateTime, formatDay } from '../../components/format';
import { Highlight } from '../../components/Highlight';
import { CheckIcon } from '../../components/Icons';
import { fr } from '../../content/fr';

const t = fr.backoffice;

function ConversationItem({
  youthId,
  conversation,
  shared,
  talents,
}: {
  youthId: string;
  conversation: Conversation;
  shared: boolean;
  talents: Skill[];
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
        <span className="mono">
          {t.conversationLabel(formatDateTime(conversation.last_message_at), conversation.message_count)}
        </span>
        {shared && (
          <button
            type="button"
            className="button button--small"
            onClick={() => void toggle()}
            aria-expanded={open}
          >
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
              <Highlight
                text={message.content}
                quote={talents.find((talent) => talent.source_message_id === message.id)?.quote}
              />
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
      setDetail(null);
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

  const { youth, skills: talents, pending_skills: pending, conversations } = detail;
  const lastActivity = conversations[0]?.last_message_at;

  return (
    <div className="stack">
      <header className="stack-sm">
        <Link to="/psy/jeunes" className="back-link">
          ← {t.back}
        </Link>
        <div className="bo__head">
          <div className="page-head">
            <h1>{youth.display_name}</h1>
            <p className="muted">
              {t.summary(conversations.length, lastActivity ? formatDay(lastActivity) : null)}
            </p>
          </div>
          <div className="bo__stats">
            <div>
              <b>{talents.length}</b>
              <span>{t.validated.toLowerCase()}</span>
            </div>
            <div>
              <b>{pending}</b>
              <span>{t.pending.toLowerCase()}</span>
            </div>
          </div>
        </div>
      </header>

      <section className="stack-sm">
        <h2>{t.talentsTitle}</h2>
        {talents.length === 0 ? (
          <p className="empty">{t.noTalents}</p>
        ) : (
          <div className="table-wrap">
            <table className="table table--stack">
              <thead>
                <tr>
                  <th scope="col">{t.talent}</th>
                  <th scope="col">{t.extract}</th>
                  <th scope="col">{t.status}</th>
                </tr>
              </thead>
              <tbody>
                {talents.map((talent) => (
                  <tr key={talent.id}>
                    <th scope="row">
                      {talent.name}
                      <span className="table__ref">
                        {fr.map.categories[talent.category] ?? talent.category} ·{' '}
                        {formatDay(talent.reviewed_at ?? talent.created_at)}
                      </span>
                    </th>
                    <td className="table__quote">« {talent.quote} »</td>
                    <td>
                      <span className="status status--on">
                        <CheckIcon />
                        {t.statusValidated}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="bo__foot">{t.onlyValidated}</p>
      </section>

      <section className="stack-sm">
        <h2>{t.conversationsTitle}</h2>
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
                talents={talents}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
