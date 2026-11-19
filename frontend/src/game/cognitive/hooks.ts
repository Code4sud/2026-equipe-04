import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent,
  type PointerEvent,
} from 'react';

/**
 * État d'un jeu lu par les minuteries et les gestes sans attendre le prochain rendu :
 * `commit` met à jour la référence et l'affichage d'un coup.
 */
export function useGameState<T>(initial: () => T) {
  const [state, setState] = useState(initial);
  const ref = useRef(state);
  useLayoutEffect(() => {
    ref.current = state;
  }, [state]);
  const commit = useCallback((change: Partial<T> | ((current: T) => T)) => {
    const next =
      typeof change === 'function' ? change(ref.current) : { ...ref.current, ...change };
    ref.current = next;
    setState(next);
  }, []);
  return [state, ref, commit] as const;
}

/**
 * Pause quand l'onglet est caché, ou à la demande. `resume` renvoie la durée de la pause
 * en millisecondes, pour la retirer des temps de réponse.
 */
export function usePause(enabled: boolean) {
  const [paused, setPaused] = useState(false);
  const since = useRef(0);
  const active = useRef(false);

  const pause = useCallback(() => {
    if (active.current) return;
    active.current = true;
    since.current = performance.now();
    setPaused(true);
  }, []);

  const resume = useCallback(() => {
    active.current = false;
    setPaused(false);
    return performance.now() - since.current;
  }, []);

  useEffect(() => {
    if (!enabled) return;
    const onChange = () => {
      if (document.visibilityState === 'hidden') pause();
    };
    document.addEventListener('visibilitychange', onChange);
    return () => document.removeEventListener('visibilitychange', onChange);
  }, [enabled, pause]);

  return { paused, pause, resume };
}

/** Raccourcis clavier, ignorés quand on tape dans un champ ou avec un modificateur. */
export function useKeys(handler: (event: KeyboardEvent) => void, enabled = true) {
  const saved = useRef(handler);
  useLayoutEffect(() => {
    saved.current = handler;
  });
  useEffect(() => {
    if (!enabled) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
      const target = event.target as HTMLElement | null;
      if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
      saved.current(event);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [enabled]);
}

/**
 * Lance `action` après `delay` ms. `token` identifie l'écran en cours : s'il change, ou si
 * `delay` passe à null (pause), la minuterie est annulée puis relancée pour le nouvel écran.
 */
export function useDelay(action: () => void, delay: number | null, token: string | number) {
  const saved = useRef(action);
  useLayoutEffect(() => {
    saved.current = action;
  });
  useEffect(() => {
    if (delay === null) return;
    const handle = window.setTimeout(() => saved.current(), delay);
    return () => window.clearTimeout(handle);
  }, [delay, token]);
}

/**
 * Bouton qui réagit dès l'appui du doigt ou de la souris, pour des temps de réponse précis.
 * Entrée et Espace passent par le clic, qui arrive alors sans compteur de clics (detail 0).
 */
export function pressProps(onPress: () => void) {
  return {
    onPointerDown: (event: PointerEvent<HTMLButtonElement>) => {
      if (event.button !== 0) return;
      event.preventDefault();
      onPress();
    },
    onClick: (event: MouseEvent<HTMLButtonElement>) => {
      if (event.detail === 0) onPress();
    },
  };
}
