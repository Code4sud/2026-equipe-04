/** Contrat de l'API du jeu : voir backend/app/game/service.py et docs/gamification.md. */

export type InstrumentKind = 'quiz' | 'questionnaire' | 'performance';
export type Tier = 'validated' | 'translated' | 'adapted' | 'custom' | 'performance' | 'talent';
export type Verdict = 'agree' | 'disagree';
export type Confidence = 'none' | 'low' | 'medium' | 'high';

export interface LikertScale {
  min: number;
  max: number;
  labels?: string[];
}

export interface ItemOption {
  id: string;
  label: string;
  emoji?: string;
  color?: string;
}

export interface GameItem {
  id: string;
  type: 'likert' | 'choice' | 'text';
  chapter?: string;
  prompt: string;
  hint?: string;
  illustration?: string;
  max_choices?: number;
  allow_text?: boolean;
  placeholder?: string;
  scale?: LikertScale;
  options?: ItemOption[];
}

export interface Chapter {
  id: string;
  title: string;
  intro?: string;
}

export interface PublicInstrument {
  id: string;
  version: number;
  kind: InstrumentKind;
  title: string;
  tagline: string;
  icon: string;
  duration_min: number;
  xp: number;
  intro?: string;
  outro?: string;
  source_note?: string;
  scale?: LikertScale;
  chapters?: Chapter[];
  min_answers?: number;
  items?: GameItem[];
  performance?: Record<string, unknown> & { scorer: string };
}

export type AnswerValue = number | string | string[] | { text: string } | null;

export interface StoredAnswer {
  item_id: string;
  value: AnswerValue;
  skipped: boolean;
}

export interface GameRun {
  id: string;
  instrument_id: string;
  instrument_version: number;
  status: 'in_progress' | 'completed';
  started_at: string;
  paused_at: string | null;
  completed_at: string | null;
  answered: number;
  seen: number;
  total: number;
}

export interface RunPayload {
  run: GameRun;
  instrument: PublicInstrument;
  answers: StoredAnswer[];
}

export interface Badge {
  id: string;
  label: string;
  description: string;
  icon: string;
  earned: boolean;
}

export interface Progress {
  xp: number;
  level: number;
  level_title: string;
  level_xp: number;
  next_level_xp: number;
  badges: Badge[];
}

export interface InstrumentSummary {
  id: string;
  kind: InstrumentKind;
  title: string;
  tagline: string;
  icon: string;
  duration_min: number;
  xp: number;
  source_note?: string | null;
  state: 'new' | 'in_progress' | 'completed';
  locked: boolean;
  replayable: boolean;
  answered: number;
  total: number;
  completed_count: number;
  last_completed_at: string | null;
}

export interface GameStatus {
  must_onboard: boolean;
  progress: Progress;
  instruments: InstrumentSummary[];
}

export interface Clan {
  id: string;
  trait: string;
  name: string;
  motto: string;
  description: string;
  icon: string;
}

export interface YouthTrait {
  id: string;
  group: string;
  kind: 'bipolar' | 'unipolar';
  value: number | null;
  confidence: Confidence;
  verdict: Verdict | null;
  label: string | null;
  low?: string;
  high?: string;
}

export interface RunResult {
  run: GameRun;
  xp_gained: number;
  progress: Progress;
  leveled_up: boolean;
  new_badges: Badge[];
  clan: Clan | null;
  highlights: YouthTrait[];
  metrics: Record<string, unknown> | null;
}

/** Masquer ou corriger ne change que la fiche du jeune : la psychologue voit tout. */
export interface GameFact {
  key: string;
  label: string;
  value: string;
  /** Réponse donnée dans le jeu, avant correction par le jeune. */
  original_value: string | null;
  edited: boolean;
  hidden: boolean;
  updated_at: string | null;
}

export interface SheetAttribute {
  id: string;
  label: string;
  description: string;
  icon: string;
  /** De 8 à 20, ou null tant qu'il n'y a pas assez de réponses. */
  score: number | null;
  /** Jeu qui peut révéler l'attribut tant que score vaut null. */
  reveal_with?: { id: string; title: string; kind: InstrumentKind } | null;
}

export interface SheetTalent {
  id: string;
  name: string;
  category: string;
  description: string;
  quote: string;
}

export interface CharacterSheet {
  identity: { display_name: string; clan: Clan | null };
  progress: Progress;
  facts: GameFact[];
  attributes: SheetAttribute[];
  trait_groups: { id: string; label: string; traits: YouthTrait[] }[];
  talents: { validated: SheetTalent[]; pending_count: number };
}

export interface GameSource {
  id: string;
  title: string;
  citation: string;
  url: string;
  licence: string;
  validated: boolean;
  adaptation: string;
  note?: string;
}

export interface InstrumentInfo {
  id: string;
  kind: InstrumentKind;
  title: string;
  tier: Tier;
  tier_label: string;
  scoring_note?: string | null;
  sources: (GameSource | null)[];
}

export interface PsyCursor {
  id: string;
  kind: 'bipolar' | 'unipolar';
  description?: string;
  reference?: string;
  norm_note?: string;
  value: number | null;
  n: number;
  confidence: Confidence;
  by_tier: Partial<Record<Tier, { value: number | null; n: number; label: string }>>;
  verdict: Verdict | null;
  headline: { percent: number; label: string } | null;
  low?: string;
  high?: string;
  label?: string;
}

export interface PsyRun extends GameRun {
  instrument: InstrumentInfo | null;
  metrics: Record<string, unknown>;
}

export interface PsyOverview {
  youth: { id: string; display_name: string };
  progress: { xp: number; level: number; level_title: string };
  clan: Clan | null;
  cursor_groups: { id: string; label: string; cursors: PsyCursor[] }[];
  /** Tous les détails, y compris ceux que le jeune a masqués de sa fiche. */
  facts: GameFact[];
  runs: PsyRun[];
}

export interface SignalRow {
  trait: string;
  trait_label?: string;
  value: number;
  weight: number;
  tier: Tier;
}

export interface ItemSourceRef {
  source_id: string;
  ref?: string;
  original?: string;
  relation?: 'verbatim' | 'translated' | 'adapted' | 'inspired';
  source: GameSource | null;
}

export interface PsyAnswerRow {
  item_id: string;
  position: number;
  chapter?: string | null;
  type: string;
  prompt: string;
  status: 'answered' | 'skipped' | 'unanswered';
  answer_label: string | null;
  value: unknown;
  hidden_by_youth: boolean;
  response_ms: number | null;
  answered_at: string | null;
  signals: SignalRow[];
  source: ItemSourceRef | null;
}

export interface PsyRunDetail {
  run: GameRun & { metrics: Record<string, unknown> };
  instrument: InstrumentInfo | null;
  run_signals: SignalRow[];
  answers: PsyAnswerRow[];
}

export interface PsyTraitSignal extends SignalRow {
  instrument_id: string | null;
  run_id: string | null;
  item_id: string | null;
  prompt: string | null;
  answer: string | null;
  at: string | null;
  tier_label: string;
  instrument_title: string | null;
  hidden_by_youth: boolean;
}

export interface PsyTraitDetail {
  cursor: PsyCursor;
  signals: PsyTraitSignal[];
}
