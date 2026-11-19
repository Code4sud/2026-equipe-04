import { useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react';
import type { MoodName } from './clips';
import type { MascotFraming, MascotStage } from './stage';

export interface MascotHandle {
  perform: (...moods: MoodName[]) => void;
}

interface MascotProps {
  ref?: Ref<MascotHandle>;
  mood: MoodName;
  framing: MascotFraming;
  className: string;
}

interface NetworkInformation {
  saveData?: boolean;
  effectiveType?: string;
}

function networkAllowsMascot(): boolean {
  const connection = (navigator as Navigator & { connection?: NetworkInformation }).connection;
  return !connection?.saveData && !['slow-2g', '2g'].includes(connection?.effectiveType ?? '');
}

/**
 * Néo en 3D. La pastille reste affichée tant que le modèle n'est pas prêt, et si l'appareil
 * ne peut pas l'afficher : l'application ne dépend jamais de lui.
 */
export function Mascot({ ref, mood, framing, className }: MascotProps) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stageRef = useRef<MascotStage | null>(null);
  const moodRef = useRef(mood);
  const pendingRef = useRef<MoodName[]>([]);
  const [ready, setReady] = useState(false);

  moodRef.current = mood;

  useImperativeHandle(
    ref,
    () => ({
      perform: (...moods) => {
        if (stageRef.current) stageRef.current.perform(moods);
        else pendingRef.current.push(...moods);
      },
    }),
    [],
  );

  useEffect(() => {
    stageRef.current?.setBase(mood);
  }, [mood]);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas || !networkAllowsMascot()) return;

    let disposed = false;
    let inView = true;
    let stage: MascotStage | null = null;
    const refreshActivity = () => stage?.setActive(inView && !document.hidden);
    const resizeObserver = new ResizeObserver(() => {
      stage?.resize(container.clientWidth, container.clientHeight);
    });
    const viewObserver = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      refreshActivity();
    });

    async function start() {
      try {
        const { createStage } = await import('./stage');
        if (disposed || !canvas) return;
        const created = await createStage(canvas, {
          framing,
          reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
          onClip: (clip) => container?.setAttribute('data-clip', clip),
        });
        if (disposed) {
          created.dispose();
          return;
        }
        stage = created;
        stageRef.current = created;
        created.setBase(moodRef.current);
        created.perform(pendingRef.current.splice(0));
        created.resize(container!.clientWidth, container!.clientHeight);
        resizeObserver.observe(container!);
        viewObserver.observe(container!);
        document.addEventListener('visibilitychange', refreshActivity);
        refreshActivity();
        setReady(true);
      } catch (error) {
        console.warn('Néo ne peut pas s’afficher sur cet appareil.', error);
      }
    }

    // Néo arrive après le contenu : il ne retarde jamais l'affichage de la page.
    const supportsIdle = typeof window.requestIdleCallback === 'function';
    const idleHandle = supportsIdle
      ? window.requestIdleCallback(() => void start(), { timeout: 1200 })
      : window.setTimeout(() => void start(), 300);

    return () => {
      disposed = true;
      if (supportsIdle) window.cancelIdleCallback(idleHandle);
      else window.clearTimeout(idleHandle);
      resizeObserver.disconnect();
      viewObserver.disconnect();
      document.removeEventListener('visibilitychange', refreshActivity);
      stage?.dispose();
      stageRef.current = null;
      setReady(false);
    };
  }, [framing]);

  return (
    <span ref={containerRef} className={`mascot ${className}`} data-ready={ready} aria-hidden="true">
      <canvas ref={canvasRef} />
    </span>
  );
}
