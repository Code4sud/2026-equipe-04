import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { errorMessage } from '../components/Feedback';
import { gameApi, type AnswerBody } from './api';
import { seededShuffle } from './seededShuffle';
import type { AnswerValue, GameItem, RunPayload, RunResult, StoredAnswer } from './types';

type Answers = Record<string, StoredAnswer>;

/** Où en était la partie à son ouverture : sert à reprendre au bon endroit. */
export interface RunStart {
  /** Réponses données (questions passées exclues). */
  answered: number;
  /** Questions déjà vues, passées comprises. */
  seen: number;
  /** Identifiants de ces questions vues : les autres sont celles de la séance qui commence. */
  seenIds: ReadonlySet<string>;
}

export interface RunPlayerOptions {
  /**
   * Questions dans un ordre tiré au hasard, propre à la partie : la graine est l'identifiant de
   * la partie, donc une reprise, sur un autre appareil comme ailleurs, suit le même ordre.
   */
  shuffle?: boolean;
}

const NOTHING_YET: RunStart = { answered: 0, seen: 0, seenIds: new Set() };

/** Questions dans l'ordre où la partie les pose. */
function orderOf(payload: RunPayload, shuffle: boolean): GameItem[] {
  const items = payload.instrument.items ?? [];
  return shuffle ? seededShuffle(items, payload.run.id) : items;
}

/**
 * Un appui reçu juste après l'affichage d'une question vient de l'écran précédent
 * (double appui, touche Entrée maintenue) : il est ignoré.
 */
const SETTLE_MS = 300;

/** Dernière réponse donnée à une question et état de son enregistrement. */
interface Save {
  /** Numéro du dernier envoi demandé : le résultat d'un envoi plus ancien ne compte plus. */
  seq: number;
  /** Seule la dernière réponse est gardée : c'est elle qui repart après un échec. */
  body: AnswerBody;
  status: 'pending' | 'saved' | 'failed';
  error: unknown;
  /** Fin du dernier envoi en file : un envoi attend toujours le précédent pour la même question. */
  queue: Promise<void>;
}

/** Valeur comparable : choix multiples dans n'importe quel ordre, espaces resserrés comme le serveur. */
function canonical(value: AnswerValue): unknown {
  if (Array.isArray(value)) return [...value].sort();
  if (value && typeof value === 'object') return { text: value.text.trim().split(/\s+/).join(' ') };
  return value;
}

function sameValue(a: AnswerValue, b: AnswerValue) {
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}

/** Une question reste à faire si elle n'a jamais été vue ou si elle a été passée. */
export function isPending(item: GameItem, answers: Answers) {
  const stored = answers[item.id];
  return !stored || stored.skipped;
}

/** Première question jamais vue après `from`, ou la fin. */
function nextUnseen(items: GameItem[], answers: Answers, from: number) {
  const found = items.findIndex((item, position) => position > from && !answers[item.id]);
  return found === -1 ? items.length : found;
}

/** Première question à faire (jamais vue ou passée) après `from`, ou la fin. */
function nextPending(items: GameItem[], answers: Answers, from: number) {
  const found = items.findIndex((item, position) => position > from && isPending(item, answers));
  return found === -1 ? items.length : found;
}

/**
 * Pilote une partie : reprise, réponse enregistrée à chaque question, retour, revue des questions
 * passées, pause et fin. L'écran avance sans attendre le réseau. Les envois d'une même question
 * partent l'un après l'autre ; la pause et la fin attendent qu'ils soient tous arrivés et renvoient
 * ceux qui ont échoué. `items` donne les questions dans l'ordre de la partie (voir `shuffle`).
 */
export function useRunPlayer(instrumentId: string, { shuffle = false }: RunPlayerOptions = {}) {
  const [payload, setPayload] = useState<RunPayload | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [xpGained, setXpGained] = useState(0);
  const [result, setResult] = useState<RunResult | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [startedWith, setStartedWith] = useState<RunStart>(NOTHING_YET);
  /** Revue des questions passées : on va de question à faire en question à faire. */
  const [reviewing, setReviewing] = useState(false);
  const saves = useRef(new Map<string, Save>());
  const lastSeq = useRef(0);
  /** Chrono de la question affichée ; il s'arrête quand l'onglet est caché. */
  const clock = useRef({ shownAt: 0, hiddenSince: null as number | null });

  const fail = useCallback((caught: unknown) => {
    setError(errorMessage(caught));
    setErrorCode(caught instanceof ApiError ? caught.code : null);
  }, []);

  const load = useCallback(async () => {
    setError(null);
    setErrorCode(null);
    try {
      const started = await gameApi.startRun(instrumentId);
      const stored = Object.fromEntries(started.answers.map((a) => [a.item_id, a]));
      const items = orderOf(started, shuffle);
      const first = items.findIndex((item) => !stored[item.id]);
      setAnswers(stored);
      setIndex(first === -1 ? items.length : first);
      setStartedWith({
        answered: started.answers.filter((a) => !a.skipped).length,
        seen: started.answers.length,
        seenIds: new Set(started.answers.map((a) => a.item_id)),
      });
      setPayload(started);
    } catch (caught) {
      fail(caught);
    }
  }, [instrumentId, shuffle, fail]);

  useEffect(() => {
    void load();
  }, [load]);

  /** Temps passé sur la question affichée, onglet visible seulement. */
  const elapsed = useCallback(() => {
    const now = performance.now();
    const { shownAt, hiddenSince } = clock.current;
    return now - shownAt - (hiddenSince === null ? 0 : now - hiddenSince);
  }, []);

  /**
   * Remet le chrono à zéro : à chaque question affichée et en quittant un écran entre deux
   * questions (accueil, chapitre, fin de série).
   */
  const markShown = useCallback(() => {
    const now = performance.now();
    clock.current = { shownAt: now, hiddenSince: document.hidden ? now : null };
  }, []);

  /** Vrai juste après l'affichage d'une question : un appui à ce moment-là est ignoré. */
  const justShown = useCallback(() => elapsed() < SETTLE_MS, [elapsed]);

  useEffect(() => {
    function onVisibilityChange() {
      const now = performance.now();
      const state = clock.current;
      if (document.hidden) {
        state.hiddenSince ??= now;
      } else if (state.hiddenSince !== null) {
        state.shownAt += now - state.hiddenSince;
        state.hiddenSince = null;
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, []);

  const items: GameItem[] = useMemo(() => (payload ? orderOf(payload, shuffle) : []), [payload, shuffle]);
  const current = items[index] ?? null;
  const shownId = current?.id;
  const runId = payload?.run.id;

  // Le chrono part quand la question s'affiche, pas au chargement de la partie.
  useEffect(() => {
    if (shownId) markShown();
  }, [shownId, markShown]);

  const refreshSaveFailed = useCallback(() => {
    setSaveFailed([...saves.current.values()].some((save) => save.status === 'failed'));
  }, []);

  const deliver = useCallback(
    async (run: string, itemId: string, save: Save, seq: number) => {
      let resent = false;
      // Si une réponse plus récente attend son tour, c'est elle qui partira : rien à envoyer.
      while (save.seq === seq) {
        try {
          const { xp_gained } = await gameApi.saveAnswer(run, itemId, save.body);
          // L'XP est acquise même si une réponse plus récente a remplacé celle-ci.
          setXpGained((total) => total + xp_gained);
          if (save.seq === seq) save.status = 'saved';
          break;
        } catch (caught) {
          if (save.seq !== seq) break;
          // Un envoi concurrent a créé la réponse juste avant : on renvoie une fois la dernière.
          if (!resent && caught instanceof ApiError && caught.code === 'already_answered') {
            resent = true;
            continue;
          }
          save.status = 'failed';
          save.error = caught;
          break;
        }
      }
      refreshSaveFailed();
    },
    [refreshSaveFailed],
  );

  /** Met la réponse en file : elle partira après l'envoi en cours pour cette question. */
  const send = useCallback(
    (run: string, itemId: string, body: AnswerBody) => {
      lastSeq.current += 1;
      const seq = lastSeq.current;
      // Un seul objet par question : un envoi en cours voit ainsi qu'une réponse plus récente l'a remplacé.
      const save: Save = saves.current.get(itemId) ?? {
        seq,
        body,
        status: 'pending',
        error: null,
        queue: Promise.resolve(),
      };
      save.seq = seq;
      save.body = body;
      save.status = 'pending';
      save.error = null;
      saves.current.set(itemId, save);
      save.queue = save.queue.then(() => deliver(run, itemId, save, seq));
      refreshSaveFailed();
    },
    [deliver, refreshSaveFailed],
  );

  /** Attend la fin de chaque envoi, y compris ceux partis pendant l'attente. */
  const drain = useCallback(async () => {
    for (;;) {
      const queues = [...saves.current.values()].map((save) => save.queue);
      await Promise.all(queues);
      if ([...saves.current.values()].every((save, position) => save.queue === queues[position])) return;
    }
  }, []);

  /** Attend les envois en cours, renvoie une fois la dernière réponse de chaque question en échec. */
  const settle = useCallback(
    async (run: string) => {
      await drain();
      for (const [itemId, save] of saves.current) {
        if (save.status === 'failed') send(run, itemId, save.body);
      }
      await drain();
      const failed = [...saves.current.values()].find((save) => save.status === 'failed');
      if (failed) throw failed.error;
    },
    [drain, send],
  );

  /** Question suivante, sans rien enregistrer ; pendant la revue, la prochaine question à faire. */
  const next = useCallback(
    () =>
      setIndex((position) =>
        reviewing ? nextPending(items, answers, position) : Math.min(position + 1, items.length),
      ),
    [reviewing, items, answers],
  );

  const record = useCallback(
    (item: GameItem, value: AnswerValue, skipped: boolean, responseMs: number) => {
      if (!runId || responseMs < SETTLE_MS) return false;
      const stored = answers[item.id];
      const unchanged =
        stored !== undefined &&
        stored.skipped === skipped &&
        (skipped || sameValue(stored.value, value));
      let after = answers;
      // Une réponse identique ne repart pas : elle garde son temps de réponse d'origine.
      if (!unchanged) {
        after = { ...answers, [item.id]: { item_id: item.id, value: skipped ? null : value, skipped } };
        setAnswers(after);
        const response_ms = Math.round(responseMs);
        send(runId, item.id, skipped ? { skipped: true, response_ms } : { value, response_ms });
      }
      // Après un retour ou une reprise, on ne refait pas défiler les questions déjà vues ; pendant
      // la revue, on va à la prochaine question passée ou jamais vue.
      setIndex(reviewing ? nextPending(items, after, index) : nextUnseen(items, after, index));
      markShown();
      return true;
    },
    [runId, answers, items, index, reviewing, send, markShown],
  );

  /**
   * Répond à la question affichée. `responseMs` sert quand l'appui précède l'envoi (animation du
   * choix). Renvoie false si l'appui est ignoré, trop tôt après l'affichage.
   */
  const answer = useCallback(
    (value: AnswerValue, responseMs = elapsed()) =>
      current ? record(current, value, false, responseMs) : false,
    [current, record, elapsed],
  );

  /**
   * Passe la question. Une question déjà vue (répondue ou déjà passée) n'a rien à enregistrer : on
   * avance comme « Suivant », d'une question ou, pendant la revue, jusqu'à la prochaine à faire.
   * Une réponse donnée n'est jamais effacée.
   */
  const skip = useCallback(() => {
    if (!current) return false;
    if (answers[current.id]) {
      if (justShown()) return false;
      next();
      markShown();
      return true;
    }
    return record(current, null, true, elapsed());
  }, [current, answers, justShown, next, markShown, record, elapsed]);

  const back = useCallback(() => setIndex((position) => Math.max(0, position - 1)), []);

  /** Revoit les questions passées ou jamais vues, dans l'ordre, sans repasser par les réponses. */
  const review = useCallback(() => {
    setReviewing(true);
    setIndex(nextPending(items, answers, -1));
  }, [items, answers]);
  /** Va directement à une question (ou à la fin avec `items.length`). */
  const goTo = useCallback(
    (position: number) => setIndex(Math.max(0, Math.min(position, items.length))),
    [items.length],
  );

  const pause = useCallback(async () => {
    if (!runId) return;
    // Une réponse encore en échec ne doit pas empêcher de faire une pause.
    await settle(runId).catch(() => undefined);
    await gameApi.pauseRun(runId);
  }, [runId, settle]);

  const finish = useCallback(
    async (trials?: unknown[]) => {
      if (!runId) return null;
      setFinishing(true);
      setError(null);
      setErrorCode(null);
      try {
        // Le serveur calcule le résultat sur les réponses reçues : toutes doivent être arrivées.
        await settle(runId);
        const completed = await gameApi.completeRun(runId, trials);
        setResult(completed);
        return completed;
      } catch (caught) {
        fail(caught);
        return null;
      } finally {
        setFinishing(false);
      }
    },
    [runId, settle, fail],
  );

  const clearError = useCallback(() => {
    setError(null);
    setErrorCode(null);
  }, []);

  const answeredCount = Object.values(answers).filter((a) => !a.skipped).length;

  return {
    instrument: payload?.instrument ?? null,
    run: payload?.run ?? null,
    items,
    index,
    current,
    answers,
    answeredCount,
    atEnd: payload !== null && index >= items.length,
    error,
    /** Code de l'API pour la dernière erreur (`not_enough_answers`, `already_completed`…). */
    errorCode,
    saveFailed,
    xpGained,
    startedWith,
    result,
    finishing,
    /** Vrai après `review()` : réponses et « Suivant » mènent à la prochaine question à faire. */
    reviewing,
    answer,
    skip,
    next,
    back,
    goTo,
    review,
    markShown,
    justShown,
    elapsed,
    pause,
    finish,
    clearError,
    reload: load,
  };
}
