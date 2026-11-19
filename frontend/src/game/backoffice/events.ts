/**
 * Historique des modifications du jeune (GET /backoffice/youths/<id>/game, champ `events`),
 * mis en mots pour la psychologue. Contrat des états avant et après : docs/gamification.md.
 */
import type { GameEvent, GameEventState, PsyCursor, Verdict } from '../types';
import { bo } from './backoffice.fr';
import { describeValue, formatDay, formatNumber } from './format';

const e = bo.events;

type Poles = Pick<PsyCursor, 'id' | 'kind' | 'low' | 'high' | 'label'>;

export interface EventLine {
  /** « Détail modifié », « Avis donné »… */
  action: string;
  /** Avant et après, quand une valeur en remplace une autre. */
  change: { before: string; after: string } | null;
  /** Ce qui a été masqué, jugé ou retiré. */
  detail: string | null;
  /** Contexte utile pour en parler : avis précédent, détail retiré de la fiche. */
  note: string | null;
}

/** Valeur brute lisible : texte, texte libre, choix multiples ou nombre. */
function plain(value: unknown): string | null {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return formatNumber(value);
  if (Array.isArray(value)) {
    const parts = value.map(plain).filter((part): part is string => Boolean(part));
    return parts.length ? parts.join(', ') : null;
  }
  if (value && typeof value === 'object' && 'text' in value) return plain((value as { text: unknown }).text);
  return null;
}

/** Détail de la fiche : `label` est son intitulé, `value` le texte du jeune. */
const factText = (state: GameEventState | null | undefined) => plain(state?.value) ?? bo.missing;

/** Réponse : `label` est le libellé choisi, `value` la valeur brute. */
const answerText = (state: GameEventState | null | undefined) =>
  state?.label ?? plain(state?.value) ?? bo.missing;

function verdictWord(verdict: Verdict | null | undefined): string {
  if (verdict === 'agree') return e.agree;
  if (verdict === 'disagree') return e.disagree;
  return e.noVerdict;
}

/** Valeur du curseur au moment de l'avis, lue comme le titre du curseur : « 72 % réservé ». */
function cursorValue(cursor: Poles | undefined, value: unknown): string | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null;
  return cursor ? describeValue(cursor, value) : bo.outOf100(formatNumber(value));
}

/** « « Pas moi » sur « Réservé·e » (72 % réservé) » */
function verdictText(state: GameEventState | null | undefined, cursor: Poles | undefined, word = true): string {
  return e.verdictOn(word ? verdictWord(state?.verdict) : '', state?.label ?? null, cursorValue(cursor, state?.value));
}

const given = (state: GameEventState | null | undefined) => (state?.at ? `, ${e.givenOn(formatDay(state.at))}` : '');

/** Une modification en mots ; `cursor` sert à lire la valeur d'un curseur comme dans le reste du panneau. */
export function describeEvent(event: GameEvent, cursor?: Poles): EventLine {
  const { before, after } = event;
  const line: EventLine = { action: e.actions[event.kind] ?? e.unknown, change: null, detail: null, note: null };
  switch (event.kind) {
    case 'fact_edited':
      return { ...line, change: { before: factText(before), after: factText(after) } };
    case 'fact_hidden':
    case 'fact_shown':
      return { ...line, detail: factText(after ?? before) };
    case 'verdict_set':
      // Un état « avant » veut dire que le jeune jugeait un autre pôle : son avis ne s'affichait plus.
      return {
        ...line,
        detail: verdictText(after, cursor),
        note: before?.verdict ? e.previous(verdictText(before, cursor)) : null,
      };
    case 'verdict_changed':
      return {
        ...line,
        change: { before: verdictWord(before?.verdict), after: verdictWord(after?.verdict) },
        detail: verdictText(after, cursor, false) || null,
      };
    case 'verdict_withdrawn':
      return { ...line, detail: `${verdictText(before, cursor)}${given(before)}` };
    case 'answer_changed':
      return { ...line, change: { before: answerText(before), after: answerText(after) } };
    case 'answer_retracted': {
      const removed = after?.fact_removed;
      return {
        ...line,
        detail: answerText(before),
        note: removed ? `${e.skipped} ${e.factRemoved(removed.label, removed.value)}` : e.skipped,
      };
    }
    default:
      return line;
  }
}
