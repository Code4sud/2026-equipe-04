import type {
  ChatEvent,
  Conversation,
  ConversationDetail,
  Privacy,
  Session,
  Skill,
  SkillList,
  SkillStatus,
  User,
  YouthDetail,
  YouthSummary,
} from './types';

const BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');

let authToken: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function configureAuth(token: string | null, unauthorized?: () => void) {
  authToken = token;
  if (unauthorized) onUnauthorized = unauthorized;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function headers(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
  };
}

async function toApiError(response: Response): Promise<ApiError> {
  const payload = await response.json().catch(() => null);
  const error = payload?.error;
  if (response.status === 401 && authToken) onUnauthorized?.();
  return new ApiError(response.status, error?.code ?? 'unknown', error?.message ?? '');
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; signal?: AbortSignal } = {},
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: options.method ?? 'GET',
    headers: headers(),
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  if (!response.ok) throw await toApiError(response);
  return response.json() as Promise<T>;
}

function parseEvent(block: string): ChatEvent | null {
  let type = '';
  let data = '';
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) type = line.slice(7);
    else if (line.startsWith('data: ')) data += line.slice(6);
  }
  return type && data ? ({ type, data: JSON.parse(data) } as ChatEvent) : null;
}

export type ReplyRequest = { content: string } | { retry: true };

/** Envoie un message et transmet la réponse du compagnon au fur et à mesure. */
export async function streamReply(
  conversationId: string,
  body: ReplyRequest,
  onEvent: (event: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${BASE_URL}/conversations/${conversationId}/messages`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw await toApiError(response);
  if (!response.body) throw new ApiError(500, 'no_stream', '');

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary = buffer.indexOf('\n\n');
    while (boundary !== -1) {
      const event = parseEvent(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      if (event) onEvent(event);
      boundary = buffer.indexOf('\n\n');
    }
  }
}

export const api = {
  login: (email: string, password: string) =>
    request<Session>('/auth/login', { method: 'POST', body: { email, password } }),
  register: (display_name: string, email: string, password: string, share_transcripts: boolean) =>
    request<Session>('/auth/register', {
      method: 'POST',
      body: { display_name, email, password, share_transcripts },
    }),
  me: (signal?: AbortSignal) => request<{ user: User }>('/auth/me', { signal }),

  openConversation: (signal?: AbortSignal) =>
    request<ConversationDetail>('/conversations', { method: 'POST', signal }),
  getConversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),
  closeConversation: (id: string) =>
    request<{ conversation: Conversation; extracting: boolean }>(`/conversations/${id}/close`, {
      method: 'POST',
    }),

  listSkills: (signal?: AbortSignal) => request<SkillList>('/me/skills', { signal }),
  refreshSkills: () => request<{ extracting: boolean }>('/me/skills/refresh', { method: 'POST' }),
  updateSkill: (id: string, changes: { status?: SkillStatus; name?: string }) =>
    request<{ skill: Skill }>(`/me/skills/${id}`, { method: 'PATCH', body: changes }),
  getPrivacy: (signal?: AbortSignal) => request<Privacy>('/me/privacy', { signal }),
  updatePrivacy: (share_transcripts: boolean) =>
    request<Privacy>('/me/privacy', { method: 'PATCH', body: { share_transcripts } }),

  listYouths: (signal?: AbortSignal) =>
    request<{ youths: YouthSummary[] }>('/backoffice/youths', { signal }),
  getYouth: (id: string, signal?: AbortSignal) =>
    request<YouthDetail>(`/backoffice/youths/${id}`, { signal }),
  getYouthConversation: (youthId: string, conversationId: string) =>
    request<ConversationDetail>(`/backoffice/youths/${youthId}/conversations/${conversationId}`),
};
