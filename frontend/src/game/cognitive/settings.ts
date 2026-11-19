/**
 * Réglages publics des jeux chronométrés (champ `performance` de l'instrument).
 * Le serveur retire `trait` et `weight` ; la clé des énigmes ne quitte jamais le serveur.
 */
import type { PublicInstrument } from '../types';

export interface SpanPhase {
  id: string | null;
  label?: string;
  backwards: boolean;
  min: number;
  max: number;
}

export interface SpanSettings {
  kind: 'corsi' | 'digits';
  phases: SpanPhase[];
  symbols: number[];
  itemMs: number;
  gapMs: number;
  practiceSpan: number;
  practiceMax: number;
  blocks: { id: number; x: number; y: number }[];
}

export interface StroopColor {
  id: string;
  label: string;
  key: string;
}

export interface StroopSettings {
  kind: 'stroop';
  colors: StroopColor[];
  trials: number;
  blocks: number;
  practiceTrials: number;
  congruentRatio: number;
  fixationMs: number;
}

export type LogicShape = 'circle' | 'square' | 'triangle' | 'diamond' | 'star' | 'hexagon' | 'arrow';
export type LogicFill = 'full' | 'empty' | 'striped';
export type LogicLine = 'h' | 'v' | 'd1' | 'd2';

export interface LogicCell {
  shape?: LogicShape;
  count?: number;
  fill?: LogicFill;
  rotate?: number;
  lines?: LogicLine[];
}

export interface LogicOption {
  id: string;
  label?: string;
  cell?: LogicCell;
}

export interface LogicPuzzle {
  id: string;
  kind: 'series' | 'matrix';
  prompt: string;
  sequence?: string[];
  grid?: (LogicCell | null)[];
  options: LogicOption[];
  /** Seulement pour l'entraînement : les énigmes comptées n'ont jamais leur réponse ici. */
  answer?: string;
  hint?: string;
}

export interface LogicSettings {
  kind: 'logic';
  practice: LogicPuzzle[];
  puzzles: LogicPuzzle[];
}

export type GameSettings = SpanSettings | StroopSettings | LogicSettings;

type Raw = Record<string, unknown>;

const DIGITS = [1, 2, 3, 4, 5, 6, 7, 8, 9];

function num(raw: Raw, key: string, fallback: number): number {
  const value = raw[key];
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function spanSettings(raw: Raw): SpanSettings {
  const phases = Array.isArray(raw.phases)
    ? (raw.phases as Raw[]).map((phase) => ({
        id: typeof phase.id === 'string' ? phase.id : null,
        label: typeof phase.label === 'string' ? phase.label : undefined,
        backwards: phase.backwards === true,
        min: num(phase, 'min_span', 2),
        max: num(phase, 'max_span', 9),
      }))
    : [
        {
          id: null,
          backwards: raw.backwards === true,
          min: num(raw, 'min_span', 2),
          max: num(raw, 'max_span', 9),
        },
      ];
  return {
    kind: raw.variant === 'corsi' ? 'corsi' : 'digits',
    phases,
    symbols: Array.isArray(raw.symbols) ? (raw.symbols as number[]) : DIGITS,
    itemMs: num(raw, 'item_ms', 700),
    gapMs: num(raw, 'gap_ms', 300),
    practiceSpan: num(raw, 'practice_span', 0),
    practiceMax: num(raw, 'practice_max', 2),
    blocks: Array.isArray(raw.blocks) ? (raw.blocks as SpanSettings['blocks']) : [],
  };
}

/** Choisit le jeu d'après `scorer` et `variant` ; null si ce navigateur ne sait pas y jouer. */
export function readSettings(instrument: PublicInstrument): GameSettings | null {
  const raw = instrument.performance as Raw | undefined;
  if (!raw) return null;
  switch (raw.scorer) {
    case 'span': {
      const settings = spanSettings(raw);
      if (settings.kind === 'corsi' && settings.blocks.length < 3) return null;
      return settings;
    }
    case 'stroop': {
      const colors = Array.isArray(raw.colors) ? (raw.colors as StroopColor[]) : [];
      if (colors.length < 2) return null;
      return {
        kind: 'stroop',
        colors,
        trials: num(raw, 'trials', 32),
        blocks: Math.max(1, num(raw, 'blocks', 1)),
        practiceTrials: num(raw, 'practice_trials', 4),
        congruentRatio: num(raw, 'congruent_ratio', 0.5),
        fixationMs: num(raw, 'fixation_ms', 500),
      };
    }
    case 'logic': {
      const puzzles = Array.isArray(raw.puzzles) ? (raw.puzzles as LogicPuzzle[]) : [];
      if (!puzzles.length) return null;
      const practice = Array.isArray(raw.practice) ? (raw.practice as LogicPuzzle[]) : [];
      return { kind: 'logic', practice, puzzles };
    }
    default:
      return null;
  }
}
