import { request } from '../api/client';
import type {
  AnswerValue,
  CharacterSheet,
  GameFact,
  GameRun,
  GameStatus,
  GameSource,
  InstrumentInfo,
  PsyOverview,
  PsyRunDetail,
  PsyTraitDetail,
  RunPayload,
  RunResult,
  Verdict,
} from './types';

export interface AnswerBody {
  value?: AnswerValue;
  skipped?: boolean;
  response_ms?: number;
}

export const gameApi = {
  status: (signal?: AbortSignal) => request<GameStatus>('/me/game', { signal }),
  setConsent: (share_game_results: boolean) =>
    request<{ share_game_results: boolean }>('/me/game/consent', {
      method: 'PATCH',
      body: { share_game_results },
    }),
  startRun: (instrumentId: string) =>
    request<RunPayload>(`/me/game/instruments/${instrumentId}/runs`, { method: 'POST' }),
  saveAnswer: (runId: string, itemId: string, body: AnswerBody) =>
    request<{ run: GameRun; xp_gained: number }>(`/me/game/runs/${runId}/answers/${itemId}`, {
      method: 'PUT',
      body,
    }),
  pauseRun: (runId: string) =>
    request<{ run: GameRun }>(`/me/game/runs/${runId}/pause`, { method: 'POST' }),
  completeRun: (runId: string, trials?: unknown[]) =>
    request<RunResult>(`/me/game/runs/${runId}/complete`, {
      method: 'POST',
      body: trials ? { trials } : {},
    }),
  sheet: (signal?: AbortSignal) => request<CharacterSheet>('/me/game/sheet', { signal }),
  updateFact: (key: string, changes: { value?: string; hidden?: boolean }) =>
    request<{ fact: GameFact }>(`/me/game/facts/${key}`, { method: 'PATCH', body: changes }),
  setTraitVerdict: (traitId: string, verdict: Verdict | null) =>
    request<{ trait_id: string; verdict: Verdict | null }>(`/me/game/traits/${traitId}/feedback`, {
      method: 'PUT',
      body: { verdict },
    }),

  psyCatalog: (signal?: AbortSignal) =>
    request<{ instruments: InstrumentInfo[]; sources: GameSource[] }>('/backoffice/game/catalog', {
      signal,
    }),
  psyOverview: (youthId: string, signal?: AbortSignal) =>
    request<PsyOverview>(`/backoffice/youths/${youthId}/game`, { signal }),
  psyRun: (youthId: string, runId: string, signal?: AbortSignal) =>
    request<PsyRunDetail>(`/backoffice/youths/${youthId}/game/runs/${runId}`, { signal }),
  psyTrait: (youthId: string, traitId: string, signal?: AbortSignal) =>
    request<PsyTraitDetail>(`/backoffice/youths/${youthId}/game/traits/${traitId}`, { signal }),
};
