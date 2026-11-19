import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { Skill, SkillStatus } from '../../api/types';
import { errorMessage } from '../../components/Feedback';
import { useYouthContext } from '../../layouts/YouthLayout';

const POLL_MS = 2500;

export type TalentChanges = { status?: SkillStatus; name?: string };

/** Talents du jeune, tenus à jour pendant que ses messages sont analysés. */
export function useTalents({ analyseOnOpen }: { analyseOnOpen: boolean }) {
  const { setPendingTalents } = useYouthContext();
  const [talents, setTalents] = useState<Skill[] | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (analyse: boolean, signal?: AbortSignal) => {
    setError(null);
    try {
      const refresh = analyse ? await api.refreshSkills() : null;
      const list = await api.listSkills(signal);
      setTalents(list.skills);
      setExtracting(Boolean(refresh?.extracting) || list.extracting);
    } catch (caught) {
      if (!signal?.aborted) setError(errorMessage(caught));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(analyseOnOpen, controller.signal);
    return () => controller.abort();
  }, [load, analyseOnOpen]);

  useEffect(() => {
    if (talents) setPendingTalents(talents.filter((t) => t.status === 'pending').length);
  }, [talents, setPendingTalents]);

  useEffect(() => {
    if (!extracting) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      api
        .listSkills(controller.signal)
        .then((list) => {
          setTalents(list.skills);
          setExtracting(list.extracting);
        })
        .catch(() => {
          if (!controller.signal.aborted) setExtracting(false);
        });
    }, POLL_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [extracting, talents]);

  const reload = useCallback(() => load(false), [load]);
  const retry = useCallback(() => load(analyseOnOpen), [load, analyseOnOpen]);

  const update = useCallback(async (id: string, changes: TalentChanges) => {
    const { skill } = await api.updateSkill(id, changes);
    setTalents((current) => current?.map((item) => (item.id === id ? skill : item)) ?? null);
  }, []);

  const add = useCallback(async (name: string, description: string) => {
    const { skill } = await api.addSkill(name, description);
    setTalents((current) => [skill, ...(current ?? [])]);
  }, []);

  return { talents, extracting, error, reload, retry, update, add };
}
