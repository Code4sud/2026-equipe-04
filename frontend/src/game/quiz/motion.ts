import { useEffect, useRef, useState, useSyncExternalStore } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

function subscribe(onChange: () => void) {
  const media = window.matchMedia(QUERY);
  media.addEventListener('change', onChange);
  return () => media.removeEventListener('change', onChange);
}

/** Vrai si la personne a demandé moins d'animations à son système. */
export function usePrefersReducedMotion() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  );
}

/**
 * Fait défiler un nombre jusqu'à sa nouvelle valeur. Sans animation si le système le demande :
 * la valeur affichée est alors toujours la vraie.
 */
export function useCountUp(
  target: number,
  { from, duration = 600 }: { from?: number; duration?: number } = {},
) {
  const reduced = usePrefersReducedMotion();
  const [shown, setShown] = useState(from ?? target);
  const latest = useRef(from ?? target);

  useEffect(() => {
    if (reduced) {
      latest.current = target;
      return;
    }
    const start = latest.current;
    if (start === target) return;
    let frame = 0;
    const began = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - began) / duration);
      const value = Math.round(start + (target - start) * (1 - (1 - progress) ** 3));
      latest.current = value;
      setShown(value);
      if (progress < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, duration, reduced]);

  return reduced ? target : shown;
}
