import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '../api/client';
import { errorMessage } from '../components/Feedback';
import { gameApi, type AnswerBody } from './api';
import type { AnswerValue, GameItem, RunPayload, RunResult, StoredAnswer } from './types';

type Answers = Record<string, StoredAnswer>;

/**
 * Pilote une partie : reprise, réponse enregistrée à chaque question, retour, pause et fin.
 * L'écran avance sans attendre le réseau ; les envois ratés repartent avant de terminer.
 */
export function useRunPlayer(instrumentId: string) {
  const [payload, setPayload] = useState<RunPayload | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [xpGained, setXpGained] = useState(0);
  const [result, setResult] = useState<RunResult | null>(null);
  const [finishing, setFinishing] = useState(false);
  const failed = useRef(new Map<string, AnswerBody>());
  const shownAt = useRef(0);

  const load = useCallback(async () => {
    setError(null);
    try {
      const next = await gameApi.startRun(instrumentId);
      const stored = Object.fromEntries(next.answers.map((a) => [a.item_id, a]));
      const items = next.instrument.items ?? [];
      const first = items.findIndex((item) => !stored[item.id]);
      setAnswers(stored);
      setIndex(first === -1 ? items.length : first);
      setPayload(next);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }, [instrumentId]);

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

  const pause = useCallback(async () => {
    if (runId) await gameApi.pauseRun(runId);
  }, [runId]);

  const finish = useCallback(
    async (trials?: unknown[]) => {
      if (!runId) return null;
      setFinishing(true);
      setError(null);
      try {
        await Promise.all(
          [...failed.current].map(async ([itemId, body]) => {
            await gameApi.saveAnswer(runId, itemId, body);
            failed.current.delete(itemId);
          }),
        );
        setSaveFailed(false);
        const next = await gameApi.completeRun(runId, trials);
        setResult(next);
        return next;
      } catch (caught) {
        setError(
          caught instanceof ApiError || caught instanceof Error
            ? errorMessage(caught)
            : errorMessage(null),
        );
        return null;
      } finally {
        setFinishing(false);
      }
    },
    [runId],
  );

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
    saveFailed,
    xpGained,
    result,
    finishing,
    answer,
    skip,
    back,
    pause,
    finish,
    reload: load,
  };
}
