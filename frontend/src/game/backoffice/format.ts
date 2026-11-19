/** Mise en forme des curseurs, scores et sources pour le backoffice. */
import type { PsyCursor, Tier } from '../types';
import { bo } from './backoffice.fr';

/** Espace fine insécable, avant « % » en français. */
const THIN = '\u202f';
const numbers = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 });
const seconds = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });
const shortDate = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'short' });
const longDate = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'long' });
const dayMonth = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' });
const clock = new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' });

/** Même ordre que la force de la preuve. */
export const TIER_ORDER: Tier[] = ['validated', 'performance', 'translated', 'adapted', 'custom', 'talent'];

/**
 * Copies de secours de TIER_WEIGHTS et CONFIDENCE_THRESHOLDS (backend/app/game/scoring.py).
 * Le panneau lit les valeurs du serveur dans GET /backoffice/game/catalog (voir method.ts).
 */
export const TIER_WEIGHTS: Record<Tier, number> = {
  validated: 1,
  performance: 1,
  translated: 0.75,
  adapted: 0.5,
  custom: 0.5,
  talent: 0.25,
};

export const CONFIDENCE_THRESHOLDS = { medium: 2, high: 5 };

export const formatNumber = (value: number) => numbers.format(value);
export const formatPercent = (value: number) => `${Math.round(value)}${THIN}%`;
export const formatShortDate = (value: string) => shortDate.format(new Date(value));
export const formatLongDate = (value: string) => longDate.format(new Date(value));

/** « 19 nov. », avec l'année seulement si ce n'est pas celle en cours. */
export function formatDay(value: string, now = new Date()): string {
  const date = new Date(value);
  const sameYear = date.getFullYear() === now.getFullYear();
  return dayMonth
    .formatToParts(date)
    .filter((part) => part.type === 'day' || part.type === 'month' || (part.type === 'year' && !sameYear))
    .map((part) => part.value)
    .join(' ');
}

/** « 19 nov. 10:42 » : date courte et heure d'une modification. */
export function formatMoment(value: string, now = new Date()): string {
  return `${formatDay(value, now)} ${clock.format(new Date(value))}`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}${THIN}ms`;
  if (ms < 60_000) return `${seconds.format(ms / 1000)}${THIN}s`;
  const total = Math.round(ms / 1000);
  return `${Math.floor(total / 60)}${THIN}min ${total % 60}${THIN}s`;
}

/** Espaces insécables du français (avant ? ! : ; »), sans toucher aux mots du contenu. */
export function frenchSpacing(text: string): string {
  return text.replace(/ ([?!:;»])/g, ' $1').replace(/« /g, '« ');
}

export function lowerFirst(text: string): string {
  return text.charAt(0).toLocaleLowerCase('fr-FR') + text.slice(1);
}

/** Libellé d'un niveau de preuve : celui que l'API envoie, sinon la copie du front (légende, méthode). */
export function tierLabel(tier: string, label?: string): string {
  return label ?? (bo.tiers as Record<string, string>)[tier] ?? tier;
}

/** Poids d'un niveau de preuve ; un niveau inconnu compte 0,5, comme côté serveur. */
export function tierWeight(tier: string, weights: Record<Tier, number> = TIER_WEIGHTS): number {
  return (weights as Record<string, number>)[tier] ?? 0.5;
}

/** Rang d'un niveau de preuve, du plus solide au plus faible ; les inconnus à la fin. */
export function tierRank(tier: string): number {
  const index = (TIER_ORDER as string[]).indexOf(tier);
  return index === -1 ? TIER_ORDER.length : index;
}

type CursorPoles = Pick<PsyCursor, 'id' | 'kind' | 'low' | 'high' | 'label'>;

/** « Réservé ↔ Sociable » ou « Intérêt manuel et technique ». */
export function cursorName(cursor: CursorPoles): string {
  if (cursor.kind === 'bipolar' && cursor.low && cursor.high) return `${cursor.low} ↔ ${cursor.high}`;
  return cursor.label ?? cursor.id;
}

/** Lit une valeur de 0 à 100 comme le titre du curseur : « 78 % réservé » ou « 70 % ». */
export function describeValue(cursor: CursorPoles, value: number): string {
  if (cursor.kind === 'bipolar' && cursor.low && cursor.high) {
    const high = value >= 50;
    return `${formatPercent(high ? value : 100 - value)} ${lowerFirst(high ? cursor.high : cursor.low)}`;
  }
  return formatPercent(value);
}

/** Comme describeValue, mais nomme aussi un curseur unipolaire : « 80 % intérêt artistique ». */
export function describeSignal(cursor: CursorPoles, value: number): string {
  if (cursor.kind === 'bipolar') return describeValue(cursor, value);
  return `${formatPercent(value)} ${lowerFirst(cursorName(cursor))}`;
}

/** « 78 % réservé », « 70 % intérêt geek et numérique » : le résultat tel que calculé par l'API. */
export function headlineText(cursor: PsyCursor): string | null {
  if (!cursor.headline) return null;
  return `${formatPercent(cursor.headline.percent)} ${lowerFirst(cursor.headline.label)}`;
}

/** Désaccord actuel : un « Pas moi » donné avant un changement de pôle n'en est plus un. */
export function disagreesNow(cursor: PsyCursor): boolean {
  return cursor.verdict === 'disagree' && !cursor.verdict_detail?.stale;
}

export interface ScaleScore {
  n: number;
  raw_sum: number;
  raw_min: number;
  raw_max: number;
  percent: number;
}

function isScale(value: unknown): value is ScaleScore {
  if (!value || typeof value !== 'object') return false;
  const scale = value as Record<string, unknown>;
  return ['n', 'raw_sum', 'raw_min', 'raw_max', 'percent'].every((key) => typeof scale[key] === 'number');
}

/** Scores bruts par échelle (questionnaires et quiz), dans metrics.scales. */
export function scaleScores(metrics: Record<string, unknown> | null | undefined): [string, ScaleScore][] {
  const scales = metrics?.scales;
  if (!scales || typeof scales !== 'object') return [];
  return Object.entries(scales as Record<string, unknown>).filter(
    (entry): entry is [string, ScaleScore] => isScale(entry[1]),
  );
}

function humanize(key: string): string {
  const text = key.replace(/_ms$/, '').replace(/_/g, ' ');
  return text.charAt(0).toLocaleUpperCase('fr-FR') + text.slice(1);
}

function formatMetric(key: string, value: number): string {
  if (key.endsWith('_ms')) return formatDuration(value);
  if (key === 'percent' || key === 'score') return bo.outOf100(formatNumber(value));
  if (key === 'accuracy') return formatPercent(value <= 1 ? value * 100 : value);
  return formatNumber(value);
}

/** Mesures d'un jeu chronométré (empan, essais, précision…), sans les scores d'échelles. */
export function performanceMetrics(
  metrics: Record<string, unknown> | null | undefined,
): { key: string; label: string; value: string }[] {
  if (!metrics) return [];
  return Object.entries(metrics).flatMap(([key, value]) => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return [{ key, label: bo.metrics[key] ?? humanize(key), value: formatMetric(key, value) }];
    }
    if (typeof value === 'boolean') {
      return [{ key, label: bo.metrics[key] ?? humanize(key), value: value ? bo.yes : bo.no }];
    }
    return [];
  });
}

/** Détail lisible d'un essai : « 8 3 8 3 → 8 3 8 4 », ou ses champs simples. */
export function trialDetail(value: unknown): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const trial = value as Record<string, unknown>;
  if (Array.isArray(trial.sequence) && Array.isArray(trial.response)) {
    const shown = (list: unknown[]) => (list.length ? list.join(' ') : bo.run.emptyResponse);
    return `${shown(trial.sequence)} → ${shown(trial.response)}`;
  }
  const parts = Object.entries(trial).flatMap(([key, field]) => {
    if (key === 'correct') return [];
    if (typeof field === 'string' || typeof field === 'number') return [`${humanize(key)}\u00a0: ${field}`];
    if (typeof field === 'boolean') return [`${humanize(key)}\u00a0: ${field ? bo.yes : bo.no}`];
    return [];
  });
  return parts.length ? parts.join(' · ') : null;
}

export function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}
