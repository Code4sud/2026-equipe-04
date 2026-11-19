export type Role = 'youth' | 'psychologist' | 'admin';
export type SkillStatus = 'pending' | 'validated' | 'rejected';

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: Role;
}

export interface Session {
  access_token: string;
  user: User;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  flags: string[];
}

export interface Conversation {
  id: string;
  status: 'active' | 'closed';
  message_count: number;
  started_at: string;
  last_message_at: string;
  closed_at: string | null;
}

export interface SafetyResource {
  nom: string;
  description: string;
  contact: string;
}

export interface SafetyInfo {
  message: string;
  resources: SafetyResource[];
}

export interface ConversationDetail {
  conversation: Conversation;
  messages: Message[];
  safety?: SafetyInfo | null;
  share_transcripts?: boolean;
}

export interface Skill {
  id: string;
  name: string;
  category: string;
  description: string;
  quote: string;
  status: SkillStatus;
  origin: 'ai' | 'youth';
  conversation_id: string | null;
  source_message_id: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface SkillEvent {
  action: 'proposed' | 'added' | 'validated' | 'rejected' | 'renamed';
  actor: 'ai' | 'youth';
  name: string;
  previous_name: string | null;
  at: string;
}

export interface TrackedSkill extends Skill {
  history: SkillEvent[];
  to_discuss: boolean;
}

export interface SkillList {
  skills: Skill[];
  extracting: boolean;
}

export interface Privacy {
  share_transcripts: boolean;
  consent_at: string | null;
}

export interface YouthSummary {
  id: string;
  display_name: string;
  share_transcripts: boolean;
  conversation_count: number;
  last_activity_at: string | null;
  validated_skills: number;
  pending_skills: number;
  rejected_skills: number;
  skills_to_discuss: number;
}

export interface YouthDetail {
  youth: Pick<YouthSummary, 'id' | 'display_name' | 'share_transcripts'> & { consent_at: string | null };
  skills: TrackedSkill[];
  pending_skills: number;
  conversations: Conversation[];
}

export type ReplyKind =
  | 'model'
  | 'reveal'
  | 'relaunch'
  | 'greeting'
  | 'followup'
  | 'encourage'
  | 'identity'
  | 'sensitive'
  | 'crisis';

export type ChatEvent =
  | { type: 'start'; data: { user_message: Message | null } }
  | { type: 'safety'; data: SafetyInfo }
  | { type: 'reply'; data: { kind: ReplyKind } }
  | { type: 'delta'; data: { text: string } }
  | {
      type: 'done';
      data: { assistant_message: Message; pending_skills: number; talent: Skill | null; extracting: boolean };
    }
  | { type: 'error'; data: { code: string } };
