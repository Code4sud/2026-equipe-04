import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, streamReply, type ReplyRequest } from '../../api/client';
import type {
  ChatEvent,
  Conversation,
  ConversationDetail,
  Message,
  SafetyInfo,
  Skill,
  SkillStatus,
} from '../../api/types';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { SendIcon, TalentStar } from '../../components/Icons';
import { SafetyCard } from '../../components/SafetyCard';
import { fr } from '../../content/fr';
import { useTalents } from './useTalents';

interface SendError {
  message: string;
  canRetry: boolean;
}

const NEAR_BOTTOM_PX = 120;
const MAX_COMPOSER_PX = 160;

function localMessage(id: string, content: string): Message {
  return { id, role: 'user', content, created_at: new Date().toISOString(), flags: [] };
}

function FoundTalent({
  talent,
  remaining,
  busy,
  onDecide,
}: {
  talent: Skill;
  remaining: number;
  busy: boolean;
  onDecide: (status: SkillStatus) => void;
}) {
  return (
    <section className="found" aria-label={fr.found.title}>
      <div className="found__top">
        <TalentStar />
        {fr.found.title}
      </div>
      <p className="found__name">{talent.name}</p>
      <blockquote className="found__quote">« {talent.quote} »</blockquote>
      <div className="actions">
        <button
          type="button"
          className="button button--small button--keep"
          disabled={busy}
          onClick={() => onDecide('validated')}
        >
          {fr.found.keep}
        </button>
        <button
          type="button"
          className="button button--small"
          disabled={busy}
          onClick={() => onDecide('rejected')}
        >
          {fr.found.reject}
        </button>
      </div>
      {remaining > 0 && (
        <Link to="/jeune/carte" className="text-link">
          {fr.found.more(remaining)}
        </Link>
      )}
    </section>
  );
}

export function ChatPage() {
  const { talents, reload: reloadTalents, update: updateTalent } = useTalents({ analyseOnOpen: false });
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [safety, setSafety] = useState<SafetyInfo | null>(null);
  const [shared, setShared] = useState(false);
  const [reply, setReply] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [talentNote, setTalentNote] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<SendError | null>(null);

  const listRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const streamRef = useRef<AbortController | null>(null);
  const followRef = useRef(true);

  const pending = (talents ?? []).filter((talent) => talent.status === 'pending');
  const found = pending
    .filter((talent) => talent.conversation_id === conversation?.id)
    .sort((a, b) => a.created_at.localeCompare(b.created_at))[0];
  const keptCount = (talents ?? []).filter((talent) => talent.status === 'validated').length;

  const applyDetail = useCallback((detail: ConversationDetail) => {
    setConversation(detail.conversation);
    setMessages(detail.messages);
    setSafety(detail.safety ?? null);
    setShared(detail.share_transcripts ?? false);
  }, []);

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoadError(null);
      try {
        applyDetail(await api.openConversation(signal));
      } catch (error) {
        if (!signal?.aborted) setLoadError(errorMessage(error));
      }
    },
    [applyDetail],
  );

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => {
      controller.abort();
      streamRef.current?.abort();
    };
  }, [load]);

  // Avant l'affichage, pour qu'un nouveau bloc ne passe pas pour un défilement du jeune.
  useLayoutEffect(() => {
    const list = listRef.current;
    if (list && followRef.current) list.scrollTop = list.scrollHeight;
  }, [messages, reply, safety, sendError, found?.id, talentNote]);

  useEffect(() => {
    const composer = composerRef.current;
    if (!composer) return;
    composer.style.height = 'auto';
    composer.style.height = `${Math.min(composer.scrollHeight, MAX_COMPOSER_PX)}px`;
  }, [draft]);

  function onScroll() {
    const list = listRef.current;
    if (list) {
      followRef.current = list.scrollHeight - list.scrollTop - list.clientHeight < NEAR_BOTTOM_PX;
    }
  }

  async function exchange(body: ReplyRequest) {
    if (!conversation) return;
    const conversationId = conversation.id;
    const tempId = `local-${Date.now()}`;
    const sentText = 'content' in body ? body.content : null;
    let started = false;
    let finished = false;
    let text = '';

    const handle = (event: ChatEvent) => {
      switch (event.type) {
        case 'start': {
          started = true;
          const stored = event.data.user_message;
          if (stored) setMessages((all) => all.map((m) => (m.id === tempId ? stored : m)));
          break;
        }
        case 'safety':
          setSafety(event.data);
          break;
        case 'delta':
          text += event.data.text;
          setReply(text);
          break;
        case 'done':
          finished = true;
          setMessages((all) => [...all, event.data.assistant_message]);
          setReply(null);
          void reloadTalents();
          break;
        case 'error':
          finished = true;
          setReply(null);
          setSendError({
            message: fr.chat.errors[event.data.code] ?? fr.chat.errors.default,
            canRetry: true,
          });
          break;
      }
    };

    followRef.current = true;
    setBusy(true);
    setSendError(null);
    setTalentNote(null);
    setReply('');
    if (sentText !== null) {
      setMessages((all) => [...all, localMessage(tempId, sentText)]);
      setDraft('');
    }

    const controller = new AbortController();
    streamRef.current = controller;
    try {
      await streamReply(conversationId, body, handle, controller.signal);
      if (!finished) {
        setReply(null);
        setSendError({ message: fr.chat.errors.default, canRetry: true });
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      setReply(null);
      if (error instanceof ApiError && error.code === 'nothing_to_retry') {
        void load();
      } else if (!started && sentText !== null) {
        setMessages((all) => all.filter((m) => m.id !== tempId));
        setDraft(sentText);
        setSendError({ message: fr.chat.notSent, canRetry: false });
      } else {
        setSendError({ message: fr.chat.errors.default, canRetry: true });
      }
    } finally {
      setBusy(false);
    }
  }

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const content = draft.trim();
    if (content && !busy) void exchange({ content });
  }

  function onComposerKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    const hasKeyboard = window.matchMedia('(hover: hover)').matches;
    if (event.key === 'Enter' && !event.shiftKey && hasKeyboard && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  async function decide(talent: Skill, status: SkillStatus) {
    setDeciding(true);
    setTalentNote(null);
    try {
      await updateTalent(talent.id, { status });
      setTalentNote(status === 'validated' ? fr.found.kept : fr.found.rejected);
    } catch (error) {
      setTalentNote(errorMessage(error));
    } finally {
      setDeciding(false);
    }
  }

  async function startNewConversation() {
    if (!conversation || busy) return;
    setBusy(true);
    setSendError(null);
    setTalentNote(null);
    try {
      await api.closeConversation(conversation.id);
      applyDetail(await api.openConversation());
      void reloadTalents();
    } catch (error) {
      setSendError({ message: errorMessage(error), canRetry: false });
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <ErrorState message={loadError} onRetry={() => void load()} />;
  if (!conversation) return <Loading />;

  return (
    <section className="chat" aria-label={fr.chat.title}>
      <div className="chat-head__wrap">
        <header className="chat-head">
          <span className="avatar" aria-hidden="true" />
          <div>
            <h1>{fr.chat.title}</h1>
            <p className="chat-head__status">
              <i />
              {fr.chat.status}
            </p>
          </div>
          <Link to="/jeune/carte" className="talent-count" aria-label={fr.chat.keptCount(keptCount)}>
            <TalentStar />
            {keptCount}
          </Link>
          <div className="chat-head__notice">
            <p className="chat__notice">
              {fr.chat.aiNotice} {shared ? fr.chat.sharedNotice : fr.chat.privateNotice}
            </p>
            {messages.length > 1 && (
              <button
                type="button"
                className="link-button"
                onClick={() => void startNewConversation()}
                disabled={busy}
              >
                {fr.chat.newConversation}
              </button>
            )}
          </div>
        </header>
      </div>

      <div className="chat__messages" ref={listRef} onScroll={onScroll}>
        <div className="chat__column" role="log" aria-live="polite" aria-relevant="additions">
          {messages.map((message) => (
            <article key={message.id} className={`bubble bubble--${message.role}`}>
              <span className="visually-hidden">
                {message.role === 'user' ? fr.chat.you : fr.chat.companion} :
              </span>
              {message.content}
            </article>
          ))}
          {reply !== null &&
            (reply ? (
              <article className="bubble bubble--assistant">{reply}</article>
            ) : (
              <div className="bubble bubble--assistant typing" role="status">
                <span className="visually-hidden">{fr.chat.thinking}</span>
                <i />
                <i />
                <i />
              </div>
            ))}
          {safety && <SafetyCard info={safety} />}
          {found && reply === null && (
            <FoundTalent
              talent={found}
              remaining={pending.length - 1}
              busy={deciding}
              onDecide={(status) => void decide(found, status)}
            />
          )}
          {talentNote && (
            <p className="chat__note" role="status">
              {talentNote}
            </p>
          )}
          {sendError && (
            <div className="chat__error" role="alert">
              <span>{sendError.message}</span>
              {sendError.canRetry && (
                <button
                  type="button"
                  className="button button--small"
                  onClick={() => void exchange({ retry: true })}
                  disabled={busy}
                >
                  {fr.common.retry}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <form className="composer" onSubmit={submit}>
        <label className="visually-hidden" htmlFor="chat-message">
          {fr.chat.placeholder}
        </label>
        <textarea
          id="chat-message"
          ref={composerRef}
          rows={1}
          maxLength={4000}
          value={draft}
          placeholder={fr.chat.placeholder}
          enterKeyHint="send"
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onComposerKey}
        />
        <button type="submit" className="composer__send" disabled={busy || !draft.trim()}>
          <SendIcon />
          <span className="visually-hidden">{fr.chat.send}</span>
        </button>
      </form>
    </section>
  );
}
