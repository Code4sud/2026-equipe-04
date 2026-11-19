import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, streamReply, type ReplyRequest } from '../../api/client';
import { useAuth } from '../../auth/AuthContext';
import type {
  ChatEvent,
  Conversation,
  ConversationDetail,
  Message,
  ReplyKind,
  SafetyInfo,
  Skill,
} from '../../api/types';
import { ChatBackdrop } from '../../components/ChatBackdrop';
import { ErrorState, errorMessage, Loading } from '../../components/Feedback';
import { SendIcon, TalentStar } from '../../components/Icons';
import { SafetyCard } from '../../components/SafetyCard';
import { fr } from '../../content/fr';
import type { MoodName } from '../../mascot/clips';
import { Mascot, type MascotHandle } from '../../mascot/Mascot';
import { useTalents } from './useTalents';

interface SendError {
  message: string;
  canRetry: boolean;
}

const NEAR_BOTTOM_PX = 120;
const MAX_COMPOSER_PX = 160;
const LAUGHTER = /\b(?:(?:ha){2,}h?|(?:hi){2,}|mdr+|ptdr+|xptdr+|lol+)\b/i;
const LAUGH_COOLDOWN_MS = 120_000;
const RECENT_REVEAL_MS = 20_000;
// Après un « Super », la carte suivante attend que Néo ait rangé la précédente.
const NEXT_CARD_DELAY_MS = 1800;
const ANNOUNCED_KEY = 'potentiel.talents-annonces';
const IMPRESSIVE_STORY_WORDS = 12;

// Sur grand écran, Néo quitte la pastille de l'en-tête et se tient en grand à côté du fil.
const WIDE_QUERY = '(min-width: 68rem)';

function subscribeWide(onChange: () => void) {
  const media = window.matchMedia(WIDE_QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}

function useWideScreen() {
  return useSyncExternalStore(subscribeWide, () => window.matchMedia(WIDE_QUERY).matches);
}

// Talents déjà montrés dans le chat, par compte : un talent trouvé pendant que le jeune était
// sur une autre page est annoncé à son retour, et aucun n'est annoncé deux fois.
function readAnnounced(userId: string): Set<string> | null {
  try {
    const raw = localStorage.getItem(`${ANNOUNCED_KEY}.${userId}`);
    return raw ? new Set(JSON.parse(raw) as string[]) : null;
  } catch {
    return null;
  }
}

function saveAnnounced(userId: string, ids: Set<string>) {
  try {
    localStorage.setItem(`${ANNOUNCED_KEY}.${userId}`, JSON.stringify([...ids]));
  } catch {
    // Stockage bloqué : les cartes restent annoncées pendant la visite.
  }
}

function isNews(talent: Skill, announced: Set<string>) {
  return talent.origin === 'ai' && talent.status === 'validated' && !announced.has(talent.id);
}

function localMessage(id: string, content: string): Message {
  return { id, role: 'user', content, created_at: new Date().toISOString(), flags: [] };
}

function FoundTalent({ talent, onClose }: { talent: Skill; onClose: () => void }) {
  return (
    <section className="found" aria-label={fr.found.title}>
      <div className="found__top">
        <TalentStar />
        {fr.found.title}
      </div>
      <p className="found__name">{talent.name}</p>
      <blockquote className="found__quote">« {talent.quote} »</blockquote>
      <div className="actions">
        <button type="button" className="button button--small button--keep" onClick={onClose}>
          {fr.found.great}
        </button>
      </div>
    </section>
  );
}

export function ChatPage() {
  const { talents, reload: reloadTalents } = useTalents({ analyseOnOpen: false });
  const wide = useWideScreen();
  const userId = useAuth().user?.id ?? 'invite';
  // Talent que Néo vient d'épingler : sa carte reste affichée jusqu'au « Super ».
  const [found, setFound] = useState<Skill | null>(null);
  // Talents trouvés pendant la discussion qui attendent leur carte, du plus ancien au plus récent.
  const [waiting, setWaiting] = useState<Skill[]>([]);
  const [nextCardAt, setNextCardAt] = useState(0);
  const announcedRef = useRef<Set<string> | null>(null);
  const foundRef = useRef<Skill | null>(null);
  foundRef.current = found;
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [safety, setSafety] = useState<SafetyInfo | null>(null);
  const [shared, setShared] = useState(false);
  const [calmReply, setCalmReply] = useState(false);
  const [reply, setReply] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [talentNote, setTalentNote] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<SendError | null>(null);

  const listRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const streamRef = useRef<AbortController | null>(null);
  const followRef = useRef(true);
  const mascotRef = useRef<MascotHandle>(null);
  const lastRevealRef = useRef(0);
  const lastLaughRef = useRef(0);
  const impressedRef = useRef(false);

  const keptCount = (talents ?? []).filter((talent) => talent.status === 'validated').length;
  const visibleTalentId = reply === null ? found?.id : undefined;

  let mascotMood: MoodName = 'idle';
  if (safety || calmReply) mascotMood = 'calm';
  else if (reply === '') mascotMood = 'think';
  else if (reply !== null) mascotMood = 'talk';
  else if (found) mascotMood = 'cardOut';
  else if (draft.trim()) mascotMood = 'listen';

  const applyDetail = useCallback((detail: ConversationDetail) => {
    setConversation(detail.conversation);
    setMessages(detail.messages);
    setSafety(detail.safety ?? null);
    setShared(detail.share_transcripts ?? false);
    setCalmReply(false);
    impressedRef.current = false;
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

  // Le fil rétrécit aussi sans nouveau message (bandeau du hackathon arrivé après lui, zone de
  // saisie qui grandit, rotation) : il reste calé sur le dernier message tant qu'on le suivait.
  const observeList = useCallback((list: HTMLDivElement) => {
    listRef.current = list;
    const observer = new ResizeObserver(() => {
      if (followRef.current) list.scrollTop = list.scrollHeight;
    });
    observer.observe(list);
    return () => {
      observer.disconnect();
      listRef.current = null;
    };
  }, []);

  // Néo n'est affiché qu'une fois la discussion chargée : il salue à ce moment-là.
  const conversationId = conversation?.id;
  const isNewConversation = messages.length === 1;
  useEffect(() => {
    if (conversationId && isNewConversation) mascotRef.current?.perform('greet');
    // Une seule fois par discussion, pas à chaque nouveau message.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  const markAnnounced = useCallback(
    (id: string) => {
      const announced = announcedRef.current ?? new Set<string>();
      announced.add(id);
      announcedRef.current = announced;
      saveAnnounced(userId, announced);
    },
    [userId],
  );

  // Chaque talent repéré par Néo a sa carte, même s'il arrive quelques secondes après la
  // réponse : l'analyse tourne en arrière-plan et useTalents la suit.
  useEffect(() => {
    if (!talents) return;
    if (!announcedRef.current) {
      const stored = readAnnounced(userId);
      if (!stored) {
        // Première ouverture sur cet appareil : les talents déjà là ne sont pas réannoncés.
        announcedRef.current = new Set(talents.map((talent) => talent.id));
        saveAnnounced(userId, announcedRef.current);
        return;
      }
      announcedRef.current = stored;
    }
    const announced = announcedRef.current;
    const news = talents
      .filter((talent) => isNews(talent, announced))
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    if (!news.length) return;
    setWaiting((current) => {
      const queued = new Set(current.map((talent) => talent.id));
      const added = news.filter((talent) => !queued.has(talent.id) && talent.id !== foundRef.current?.id);
      return added.length ? [...current, ...added] : current;
    });
  }, [talents, userId]);

  // Une carte à la fois, jamais pendant que Néo répond.
  useEffect(() => {
    if (found || reply !== null || !waiting.length) return;
    const timer = window.setTimeout(() => {
      const [next, ...rest] = waiting;
      markAnnounced(next.id);
      // Néo refait sa détection pour chaque talent, même juste après le précédent.
      lastRevealRef.current = 0;
      setWaiting(rest);
      setTalentNote(null);
      setFound(next);
    }, Math.max(0, nextCardAt - Date.now()));
    return () => window.clearTimeout(timer);
  }, [found, reply, waiting, nextCardAt, markAnnounced]);

  // Un talent repéré : Néo le détecte (sauf s'il vient de l'annoncer), puis sort sa carte.
  useEffect(() => {
    if (!visibleTalentId) return;
    if (Date.now() - lastRevealRef.current > RECENT_REVEAL_MS) mascotRef.current?.perform('reveal');
    lastRevealRef.current = Date.now();
  }, [visibleTalentId]);

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

  function reactToReply(kind: ReplyKind, sentText: string | null) {
    setCalmReply(kind === 'sensitive');
    if (kind === 'relaunch') {
      mascotRef.current?.perform('shrug');
    } else if (kind === 'encourage') {
      mascotRef.current?.perform('cheer');
    } else if (kind === 'reveal') {
      lastRevealRef.current = Date.now();
      mascotRef.current?.perform('reveal');
    } else if (
      kind === 'model' &&
      !impressedRef.current &&
      sentText &&
      sentText.trim().split(/\s+/).length >= IMPRESSIVE_STORY_WORDS
    ) {
      impressedRef.current = true;
      mascotRef.current?.perform('impressed');
    }
  }

  function laughAlong(sentText: string | null) {
    if (!sentText || !LAUGHTER.test(sentText)) return;
    if (Date.now() - lastLaughRef.current < LAUGH_COOLDOWN_MS) return;
    lastLaughRef.current = Date.now();
    mascotRef.current?.perform('laugh');
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
        case 'reply':
          reactToReply(event.data.kind, sentText);
          break;
        case 'delta':
          text += event.data.text;
          setReply(text);
          break;
        case 'done':
          finished = true;
          setMessages((all) => [...all, event.data.assistant_message]);
          setReply(null);
          laughAlong(sentText);
          if (event.data.talent) {
            // Néo vient de l'annoncer dans sa réponse : sa carte passe devant les autres.
            const talent = event.data.talent;
            const shown = foundRef.current;
            markAnnounced(talent.id);
            setWaiting((current) => [
              ...(shown && shown.id !== talent.id ? [shown] : []),
              ...current.filter((item) => item.id !== talent.id),
            ]);
            setFound(talent);
          }
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

  function celebrate() {
    setFound(null);
    setNextCardAt(Date.now() + NEXT_CARD_DELAY_MS);
    setTalentNote(fr.found.kept);
    mascotRef.current?.perform('cardKeep', 'cheer');
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
      <ChatBackdrop />
      {wide && (
        <div className="chat__stage">
          <Mascot ref={mascotRef} mood={mascotMood} framing="full" className="mascot--stage" />
        </div>
      )}
      <div className="chat-head__wrap">
        <header className={wide ? 'chat-head chat-head--solo' : 'chat-head'}>
          {!wide && <Mascot ref={mascotRef} mood={mascotMood} framing="portrait" className="mascot--chat" />}
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

      <div className="chat__messages" ref={observeList} onScroll={onScroll}>
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
            <FoundTalent talent={found} onClose={celebrate} />
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
