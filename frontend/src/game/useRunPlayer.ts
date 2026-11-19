import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { errorMessage } from '../components/Feedback';
import { gameApi, type AnswerBody } from './api';
import type { AnswerValue, GameItem, RunPayload, RunResult, StoredAnswer } from './types';

type Answers = Record<string, StoredAnswer>;

/** Où en était la partie à son ouverture : sert à reprendre au bon endroit. */
export interface RunStart {
  /** Réponses données (questions passées exclues). */
  answered: number;
  /** Questions déjà vues, passées comprises. */
  seen: number;
}

const NOTHING_YET: RunStart = { answered: 0, seen: 0 };

/**
 * Pilote une partie : reprise, réponse enregistrée à chaque question, retour, pause et fin.
 * L'écran avance sans attendre le réseau ; les envois ratés repartent avant la pause et la fin.
 */
export function useRunPlayer(instrumentId: string) {
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
  const failed = useRef(new Map<string, AnswerBody>());
  const shownAt = useRef(0);

  const fail = useCallback((caught: unknown) => {
    setError(errorMessage(caught));
    setErrorCode(caught instanceof ApiError ? caught.code : null);
  }, []);

  const load = useCallback(async () => {
    setError(null);
    setErrorCode(null);
    try {
      const next = await gameApi.startRun(instrumentId);
      const stored = Object.fromEntries(next.answers.map((a) => [a.item_id, a]));
      const items = next.instrument.items ?? [];
      const first = items.findIndex((item) => !stored[item.id]);
      setAnswers(stored);
      setIndex(first === -1 ? items.length : first);
      setStartedWith({
        answered: next.answers.filter((a) => !a.skipped).length,
        seen: next.answers.length,
      });
      setPayload(next);
    } catch (caught) {
      fail(caught);
    }
  }, [instrumentId, fail]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    shownAt.current = performance.now();
  }, [index]);

  const items: GameItem[] = useMemo(() => payload?.instrument.items ?? [], [payload]);
  const current = items[index] ?? null;
  const runId = payload?.run.id;

  const send = useCallback(
    (itemId: string, body: AnswerBody) => {
      if (!runId) return;
      gameApi
        .saveAnswer(runId, itemId, body)
        .then(({ xp_gained }) => {
          failed.current.delete(itemId);
          setSaveFailed(failed.current.size > 0);
          setXpGained((total) => total + xp_gained);
        })
        .catch(() => {
          failed.current.set(itemId, body);
          setSaveFailed(true);
        });
    },
    [runId],
  );

  /** Renvoie les réponses dont l'envoi a échoué. Rejette si le réseau manque encore. */
  const flush = useCallback(async () => {
    if (!runId) return;
    await Promise.all(
      [...failed.current].map(async ([itemId, body]) => {
        const { xp_gained } = await gameApi.saveAnswer(runId, itemId, body);
        failed.current.delete(itemId);
        setXpGained((total) => total + xp_gained);
      }),
    );
    setSaveFailed(failed.current.size > 0);
  }, [runId]);

  const record = useCallback(
    (item: GameItem, value: AnswerValue, skipped: boolean) => {
      const response_ms = Math.round(performance.now() - shownAt.current);
      setAnswers((all) => ({ ...all, [item.id]: { item_id: item.id, value, skipped } }));
      send(item.id, skipped ? { skipped: true, response_ms } : { value, response_ms });
      setIndex((position) => position + 1);
    },
    [send],
  );

  const answer = useCallback(
    (value: AnswerValue) => {
      if (current) record(current, value, false);
    },
    [current, record],
  );
  const skip = useCallback(() => {
    if (current) record(current, null, true);
  }, [current, record]);
  const back = useCallback(() => setIndex((position) => Math.max(0, position - 1)), []);
  /** Va directement à une question (ou à la fin avec `items.length`). */
  const goTo = useCallback(
    (position: number) => setIndex(Math.max(0, Math.min(position, items.length))),
    [items.length],
  );

  const pause = useCallback(async () => {
    if (!runId) return;
    // Une réponse encore en échec ne doit pas empêcher de faire une pause.
    await flush().catch(() => undefined);
    await gameApi.pauseRun(runId);
  }, [runId, flush]);

  const finish = useCallback(
    async (trials?: unknown[]) => {
      if (!runId) return null;
      setFinishing(true);
      setError(null);
      setErrorCode(null);
      try {
        await flush();
        const next = await gameApi.completeRun(runId, trials);
        setResult(next);
        return next;
      } catch (caught) {
        fail(caught);
        return null;
      } finally {
        setFinishing(false);
      }
    },
    [runId, flush, fail],
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
    answer,
    skip,
    back,
    goTo,
    pause,
    finish,
    clearError,
    reload: load,
  };
}
