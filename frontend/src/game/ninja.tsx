import { createContext, useContext, useEffect, useRef, useState } from 'react';
import './ninja.css';
import type { AnswerValue, GameItem, LikertScale } from './types';

/*
 * Mode ninja, pour la démo de présentation : le jeu se joue tout seul, à un rythme visible, pour
 * montrer au jury comment fonctionne chaque test. Un second appui sur le bouton l'arrête.
 */

/** Temps de réponse minimal envoyé : le serveur ignore les appuis de moins de 300 ms. */
export const NINJA_RESPONSE_MS = 400;
const NINJA_TEXTS = ['Toujours partant', 'Un pas après l’autre', 'Faire rire les autres', 'Le dessin', 'La musique'];

export function pickOne<T>(list: readonly T[]): T {
  return list[Math.floor(Math.random() * list.length)];
}

/** Une réponse au hasard, valable pour la question. */
export function ninjaValue(item: GameItem, scale?: LikertScale): AnswerValue {
  if (item.type === 'likert') {
    const range = item.scale ?? scale;
    return range ? range.min + Math.floor(Math.random() * (range.max - range.min + 1)) : 3;
  }
  if (item.options?.length) {
    const id = pickOne(item.options).id;
    return (item.max_choices ?? 1) > 1 ? [id] : id;
  }
  return { text: pickOne(NINJA_TEXTS) };
}

export interface Ninja {
  active: boolean;
  toggle: () => void;
  stop: () => void;
}

export function useNinjaState(): Ninja {
  const [active, setActive] = useState(false);
  return { active, toggle: () => setActive((on) => !on), stop: () => setActive(false) };
}

/** Pour les jeux chronométrés : leurs écrans lisent le mode ninja sans le recevoir en props. */
export const NinjaContext = createContext<Ninja | null>(null);

export function useNinja(): boolean {
  return useContext(NinjaContext)?.active ?? false;
}

/**
 * Joue l'étape de l'écran affiché `delayMs` après chaque rendu, tant que le mode est actif :
 * tout nouveau rendu (le jeu a avancé) relance le minuteur avec l'action du moment.
 */
export function useNinjaStep(active: boolean, action: (() => void) | null, delayMs: number) {
  const saved = useRef(action);
  saved.current = action;
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active || !action) return;
    const timer = window.setTimeout(() => {
      const act = saved.current;
      if (!act) return;
      act();
      setTick((tick) => tick + 1);
    }, delayMs);
    return () => window.clearTimeout(timer);
  });
}

export function NinjaButton({ ninja }: { ninja: Ninja | null }) {
  if (!ninja) return null;
  return (
    <button
      type="button"
      className={`ninja-button${ninja.active ? ' ninja-button--on' : ''}`}
      aria-pressed={ninja.active}
      title="Mode ninja : le jeu se joue tout seul (démo)"
      onClick={ninja.toggle}
    >
      <span aria-hidden="true">🥷</span> {ninja.active ? 'Stop' : 'Ninja'}
    </button>
  );
}

/** Le bouton des jeux chronométrés, d'après le contexte. */
export function NinjaContextButton() {
  return <NinjaButton ninja={useContext(NinjaContext)} />;
}
