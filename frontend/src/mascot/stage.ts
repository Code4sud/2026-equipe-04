/**
 * Rendu 3D de Néo. Ce module et three.js sont chargés à part, seulement quand Néo s'affiche.
 */
import {
  AnimationMixer,
  DirectionalLight,
  HemisphereLight,
  LoopOnce,
  LoopRepeat,
  Mesh,
  PerspectiveCamera,
  Scene,
  Vector3,
  WebGLRenderer,
  type AnimationAction,
  type Object3D,
} from 'three';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js';
import { clone as cloneSkinnedModel } from 'three/addons/utils/SkeletonUtils.js';
import { chooseClip, INTERRUPTING_MOODS, MOODS, type MoodName } from './clips';
import modelUrl from './neo.glb?url';

export type MascotFraming = 'portrait' | 'full';

interface StageOptions {
  framing: MascotFraming;
  reducedMotion: boolean;
  onClip: (clip: string) => void;
}

const FRAME_MS = 1000 / 30;
const MAX_PIXEL_RATIO = 2;
const FADE_SECONDS = 0.3;
const FIELD_OF_VIEW = 20;
const FOLLOW_SPEED = 5;
/** Hauteur visible autour du point suivi, en unités du modèle. */
const FRAMINGS = {
  portrait: { height: 1.3, offsetY: 0 },
  full: { height: 2.16, offsetY: 0 },
} as const;

let modelPromise: Promise<GLTF> | null = null;

function loadModel(): Promise<GLTF> {
  modelPromise ??= new GLTFLoader()
    .setMeshoptDecoder(MeshoptDecoder)
    .loadAsync(modelUrl)
    .catch((error: unknown) => {
      modelPromise = null;
      throw error;
    });
  return modelPromise;
}

export class MascotStage {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(FIELD_OF_VIEW, 1, 0.1, 30);
  private readonly mixer: AnimationMixer;
  private readonly actions = new Map<string, AnimationAction>();
  private readonly head: Object3D | undefined;
  private readonly lookAt = new Vector3();
  private readonly headPosition = new Vector3();

  private base: MoodName = 'idle';
  private queue: MoodName[] = [];
  private performing = false;
  private current: AnimationAction | null = null;
  private turn = 0;
  private frame = 0;
  private lastFrame = 0;
  private active = false;

  constructor(
    canvas: HTMLCanvasElement,
    model: GLTF,
    private readonly options: StageOptions,
  ) {
    this.renderer = new WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: 'low-power' });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, MAX_PIXEL_RATIO));

    this.scene.add(new HemisphereLight(0xfff6e8, 0xe8c9a8, 2.1));
    const sun = new DirectionalLight(0xfff1dc, 1.9);
    sun.position.set(1.4, 2.6, 3.2);
    this.scene.add(sun);

    const character = cloneSkinnedModel(model.scene);
    character.traverse((node) => {
      // Les animations déplacent les sommets hors de la boîte calculée au repos.
      if (node instanceof Mesh) node.frustumCulled = false;
    });
    this.scene.add(character);
    this.head = character.getObjectByName('head');

    this.mixer = new AnimationMixer(character);
    for (const clip of model.animations) this.actions.set(clip.name, this.mixer.clipAction(clip));
    this.mixer.addEventListener('finished', (event) => {
      if (event.action === this.current && this.performing) this.advance();
    });
    this.advance();
    this.mixer.update(0);
    this.followHead(1);
  }

  resize(width: number, height: number): void {
    if (!width || !height) return;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.render();
  }

  /** État de fond, repris dès qu'aucun geste n'est en cours. */
  setBase(mood: MoodName): void {
    if (mood === this.base) return;
    this.base = mood;
    if (INTERRUPTING_MOODS.has(mood)) {
      this.queue = [];
      this.performing = false;
    }
    if (!this.performing) this.advance();
  }

  /** Enchaîne des gestes ponctuels, puis revient à l'état de fond. */
  perform(moods: MoodName[]): void {
    if (this.base === 'calm' || this.options.reducedMotion) return;
    this.queue.push(...moods);
    if (!this.performing) this.advance();
  }

  setActive(active: boolean): void {
    if (active === this.active) return;
    this.active = active;
    cancelAnimationFrame(this.frame);
    if (active && !this.options.reducedMotion) {
      this.lastFrame = performance.now();
      this.frame = requestAnimationFrame(this.tick);
    }
  }

  dispose(): void {
    this.setActive(false);
    this.mixer.stopAllAction();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
  }

  private advance(): void {
    while (this.queue.length) {
      const mood = this.queue.shift() as MoodName;
      if (this.play(mood)) {
        this.performing = true;
        return;
      }
    }
    this.performing = false;
    this.play(this.base);
  }

  private play(mood: MoodName): boolean {
    const definition = MOODS[mood];
    const clip = chooseClip(mood, [...this.actions.keys()], this.turn);
    const action = clip ? this.actions.get(clip) : undefined;
    if (!clip || !action) return false;
    if (mood === 'talk') this.turn += 1;

    const previous = this.current;
    if (action === previous && definition.playback === 'loop') return true;

    action.reset();
    action.setLoop(definition.playback === 'loop' ? LoopRepeat : LoopOnce, Infinity);
    action.clampWhenFinished = definition.playback !== 'loop';
    if (this.options.reducedMotion) {
      previous?.stop();
      action.play();
      action.paused = true;
      action.time = action.getClip().duration * 0.25;
    } else {
      action.play();
      if (previous && previous !== action) previous.crossFadeTo(action, FADE_SECONDS, false);
    }
    this.current = action;
    this.options.onClip(clip);
    if (this.options.reducedMotion) {
      this.mixer.update(0);
      this.render();
    }
    return true;
  }

  private followHead(amount: number): void {
    const framing = FRAMINGS[this.options.framing];
    let targetX = 0;
    let targetY = framing.offsetY;
    if (this.options.framing === 'portrait' && this.head) {
      this.head.getWorldPosition(this.headPosition);
      targetX = this.headPosition.x * 0.7;
      targetY += this.headPosition.y;
    }
    this.lookAt.x += (targetX - this.lookAt.x) * amount;
    this.lookAt.y += (targetY - this.lookAt.y) * amount;
    const distance = framing.height / 2 / Math.tan((FIELD_OF_VIEW * Math.PI) / 360);
    this.camera.position.set(this.lookAt.x, this.lookAt.y, distance);
    this.camera.lookAt(this.lookAt);
  }

  private render(): void {
    this.renderer.render(this.scene, this.camera);
  }

  private readonly tick = (now: number): void => {
    this.frame = requestAnimationFrame(this.tick);
    const elapsed = now - this.lastFrame;
    if (elapsed < FRAME_MS) return;
    this.lastFrame = now;
    const seconds = Math.min(elapsed / 1000, 0.1);
    this.mixer.update(seconds);
    this.followHead(1 - Math.exp(-FOLLOW_SPEED * seconds));
    this.render();
  };
}

export async function createStage(canvas: HTMLCanvasElement, options: StageOptions): Promise<MascotStage> {
  return new MascotStage(canvas, await loadModel(), options);
}
