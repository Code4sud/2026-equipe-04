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

/**
 * Archétype : badge ludique tiré du curseur de caractère le plus marqué, recalculé à chaque
 * réponse (backend/app/game/service.py, archetype_for). Le jeune ne voit ni le curseur, ni le
 * pôle, ni la valeur qui le désignent.
 */
export interface Archetype {
  id: string;
  name: string;
  motto: string;
  description: string;
  emoji: string;
  /** Pôle tel que le jeune le voit (« Sociable », « Posé·e »), ou « Entre les deux » pour Le Caméléon. */
  quality: string;
}

/** Côté psychologue : le curseur et le pôle qui désignent l'archétype (GET /backoffice/game/catalog). */
export interface PsyArchetypeInfo extends Archetype {
  /** Null pour l'archétype équilibré, qu'aucun curseur ne désigne. */
  trait: string | null;
  pole: 'low' | 'high' | 'balanced';
  /** « Réservé ↔ Sociable » ; null pour l'archétype équilibré. */
  trait_label: string | null;
  /** « Sociable », ou « Entre les deux » pour l'archétype équilibré. */
  pole_label: string;
}

/** Archétype d'un jeune pour la psychologue, avec la valeur du curseur qui l'a désigné. */
export interface PsyArchetype extends PsyArchetypeInfo {
  /** Valeur brute de 0 à 100 du curseur ; null pour l'archétype équilibré. */
  value: number | null;
}

/** Un curseur à un seul pôle n'apparaît au jeune que comme point fort (valeur de 50 ou plus). */
export interface YouthTrait {
  id: string;
  group: string;
  kind: 'bipolar' | 'unipolar';
  value: number | null;
  confidence: Confidence;
  /**
   * Avis du jeune sur ce qu'il voit maintenant. Null s'il n'a rien dit, ou si le curseur
   * bipolaire a changé de pôle (label) depuis son avis : il peut alors juger à nouveau.
   */
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
  archetype: Archetype | null;
  /**
   * Archétype d'avant quand cette partie l'a fait changer (il suit le trait de caractère le plus
   * marqué), sinon null, comme pour le résultat redemandé d'une partie déjà terminée.
   */
  previous_archetype?: Archetype | null;
  highlights: YouthTrait[];
  /**
   * Jeux chronométrés : les réussites du jeune seulement (record, séries, meilleure série,
   * énigmes résolues...), jamais un pourcentage. Null pour un quiz ou un questionnaire.
   */
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
  /** Dernière correction de la valeur par le jeune (masquer n'en est pas une), sinon null. */
  edited_at: string | null;
  /** Psychologue seulement : jeu et question d'où vient le détail. */
  source_instrument_id?: string | null;
  source_item_id?: string | null;
}

export interface SheetAttribute {
  id: string;
  label: string;
  description: string;
  icon: string;
  /**
   * De 10 à 20, calculé sur les seuls points forts (curseurs à 50 ou plus) : un jeu raté ou un
   * pôle bas ne le fait jamais baisser. Null tant qu'aucun point fort n'est connu.
   */
  score: number | null;
  /** Jeu qui peut révéler l'attribut tant que score vaut null. */
  reveal_with?: { id: string; title: string; kind: InstrumentKind } | null;
}

export interface SheetTalent {
  id: string;
  name: string;
  /** Catégorie de Néo ; un talent ajouté par le jeune n'a que la catégorie par défaut. */
  category: string;
  description: string;
  quote: string;
  /** « ai » : repéré par Néo, compte pour les curseurs et l'XP ; « youth » : ajouté par le jeune. */
  origin?: 'ai' | 'youth';
}

export interface CharacterSheet {
  identity: { display_name: string; archetype: Archetype | null };
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
  /** Titres des chapitres : les réponses ne portent que l'identifiant du chapitre. */
  chapters: Pick<Chapter, 'id' | 'title'>[];
}

/** GET /backoffice/game/catalog */
export interface PsyCatalog {
  instruments: InstrumentInfo[];
  sources: GameSource[];
  /** Poids de chaque niveau de preuve dans les curseurs (backend/app/game/scoring.py). */
  weights: Record<Tier, number>;
  /** Poids total minimal d'une confiance moyenne et bonne ; en dessous : faible, à 0 : aucune. */
  confidence_thresholds: { medium: number; high: number };
}

/** Ce que le jeune a jugé avec « C'est moi » ou « Pas moi », et quand. */
export interface VerdictDetail {
  verdict: Verdict;
  /** Libellé montré au jeune au moment du verdict (« Réservé·e », « Entre les deux »...). */
  label_at_verdict: string | null;
  value_at_verdict: number | null;
  at: string | null;
  /** Le curseur a changé de pôle depuis : le jeune ne voit plus ce verdict et peut juger à nouveau. */
  stale: boolean;
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
  /** Dernier verdict enregistré, même s'il portait sur l'autre pôle : voir verdict_detail. */
  verdict: Verdict | null;
  verdict_detail: VerdictDetail | null;
  headline: { percent: number; label: string } | null;
  low?: string;
  high?: string;
  label?: string;
}

export interface PsyRun extends GameRun {
  instrument: InstrumentInfo | null;
  metrics: Record<string, unknown>;
}

export type GameEventKind =
  | 'fact_edited'
  | 'fact_hidden'
  | 'fact_shown'
  | 'verdict_set'
  | 'verdict_changed'
  | 'verdict_withdrawn'
  | 'answer_changed'
  | 'answer_retracted';

/** Ce que l'événement concerne : un détail de la fiche, un curseur ou une réponse d'une partie. */
export type GameEventRef =
  | { type: 'fact'; key: string }
  | { type: 'trait'; trait_id: string }
  | { type: 'answer'; run_id: string; item_id: string; instrument_id: string | null };

/** État avant ou après une modification ; les champs présents dépendent du type d'événement. */
export interface GameEventState {
  /** Détail : son intitulé ; verdict : le libellé jugé ; réponse : le libellé choisi. */
  label?: string | null;
  /** Détail : son texte ; verdict : la valeur du curseur ; réponse : la valeur brute. */
  value?: unknown;
  hidden?: boolean;
  verdict?: Verdict | null;
  /** Verdict remplacé ou retiré : quand il avait été donné. */
  at?: string | null;
  skipped?: boolean;
  /** Réponse retirée : le détail qui a quitté la fiche, s'il venait de cette réponse. */
  fact_removed?: { key: string; label: string; value: string } | null;
}

/** Modification faite par le jeune, pour que la psychologue puisse lui en parler. */
export interface GameEvent {
  id: number;
  kind: GameEventKind;
  /** Ce qui a changé, en clair : « Passion », « Réservé ↔ Sociable », « Quiz d'arrivée · Ta couleur ? ». */
  subject: string;
  ref: GameEventRef;
  before: GameEventState | null;
  after: GameEventState | null;
  at: string;
}

export interface PsyOverview {
  youth: { id: string; display_name: string };
  progress: { xp: number; level: number; level_title: string };
  /** Null tant qu'aucun curseur de caractère n'a de valeur. */
  archetype: PsyArchetype | null;
  cursor_groups: { id: string; label: string; cursors: PsyCursor[] }[];
  /** Tous les détails, y compris ceux que le jeune a masqués de sa fiche. */
  facts: GameFact[];
  runs: PsyRun[];
  /** Modifications du jeune, de la plus récente à la plus ancienne (200 au plus). */
  events: GameEvent[];
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
  /** Choix proposés au jeune (questions à choix), sinon null. */
  options: { id: string; label: string }[] | null;
  /** Échelle proposée au jeune (questions Likert), sinon null. */
  scale: LikertScale | null;
  /** Le jeune a masqué de sa fiche le détail venu de cette question (même jeu, même question). */
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
