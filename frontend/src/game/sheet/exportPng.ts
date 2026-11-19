/**
 * Dessine la fiche en PNG, entièrement dans le navigateur : aucun service externe.
 * Les dessins viennent des mêmes chemins SVG que la page (Path2D), les couleurs de tokens.css.
 * Les détails masqués par le jeune ne figurent jamais sur l'image.
 */
import { fr } from '../../content/fr';
import type { Archetype, CharacterSheet, GameFact } from '../types';
import { isColorFact, swatchFor } from './colors';
import { orderFacts } from './facts';
import { glyphFor, sealPath, type GlyphPath } from './glyphs';
import { quote, sheetFr, typo } from './sheet.fr';

// Portrait, de 1080 x 1350 à environ 1080 x 1930 selon ce que la fiche contient.
const WIDTH = 1080;
const MIN_HEIGHT = 1350;
const MARGIN = 96;
const SECTION_GAP = 60;
const INNER = WIDTH - MARGIN * 2;
const MAX_TALENTS = 5;
const MAX_FACTS = 6;
// Même dessin que TalentStarShape (components/Icons.tsx), sur une grille de 40.
const TALENT_STAR = 'M20 9.5l3.1 6.4 7 1-5.1 4.9 1.2 7-6.2-3.3-6.2 3.3 1.2-7-5.1-4.9 7-1z';
const CORNER: GlyphPath[] = [{ d: 'M4 30V10a6 6 0 0 1 6-6h20M9 22v-8a5 5 0 0 1 5-5h8' }];

const FONTS = {
  heading: (size: number, weight = 800) => `${weight} ${size}px "Baloo 2", sans-serif`,
  body: (size: number, weight = 600) => `${weight} ${size}px Figtree, sans-serif`,
  mono: (size: number, weight = 500) => `${weight} ${size}px "DM Mono", monospace`,
  emoji: (size: number) => `${size}px "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif`,
};

interface Palette {
  bg: string;
  surface: string;
  muted: string;
  border: string;
  text: string;
  textMuted: string;
  accent: string;
  accentSoft: string;
  accentText: string;
  talent: string;
  talentSoft: string;
  talentText: string;
  talentStar: string;
  onAccent: string;
  peach: string;
  /** Médaillon de l'archétype : crème dans les deux thèmes, comme à l'écran. */
  medal: string;
  onMedal: string;
  paper: string;
  line: string;
  softLine: string;
}

/** Mélange deux couleurs hexadécimales, comme color-mix(in srgb) dans la feuille de style. */
function mix(first: string, second: string, weight: number) {
  const parse = (hex: string) => {
    const value = hex.replace('#', '');
    const full = value.length === 3 ? [...value].map((c) => c + c).join('') : value;
    return [0, 2, 4].map((index) => parseInt(full.slice(index, index + 2), 16));
  };
  const [a, b] = [parse(first), parse(second)];
  if ([...a, ...b].some(Number.isNaN)) return first;
  const channels = a.map((channel, index) => Math.round(channel * weight + b[index] * (1 - weight)));
  return `rgb(${channels.join(' ')})`;
}

function readPalette(): Palette {
  const style = getComputedStyle(document.documentElement);
  const token = (name: string) => style.getPropertyValue(name).trim();
  const surface = token('--color-surface');
  const muted = token('--color-surface-muted');
  const text = token('--color-text');
  return {
    bg: token('--color-bg'),
    surface,
    muted,
    border: token('--color-border'),
    text,
    textMuted: token('--color-text-muted'),
    accent: token('--color-accent'),
    accentSoft: token('--color-accent-soft'),
    accentText: token('--color-accent-text'),
    talent: token('--color-talent'),
    talentSoft: token('--color-talent-soft'),
    talentText: token('--color-talent-text'),
    talentStar: token('--color-talent-star'),
    onAccent: token('--color-on-accent'),
    peach: token('--color-peach'),
    medal: token('--color-medal'),
    onMedal: token('--color-on-medal'),
    paper: mix(surface, muted, 0.78),
    line: mix(text, surface, 0.3),
    softLine: mix(text, surface, 0.16),
  };
}

function drawPaths(
  ctx: CanvasRenderingContext2D,
  paths: GlyphPath[],
  x: number,
  y: number,
  scale: number,
  color: string,
  lineWidth = 1.8,
) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(scale, scale);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  for (const path of paths) {
    const shape = new Path2D(path.d);
    if (path.fill) ctx.fill(shape);
    else ctx.stroke(shape);
  }
  ctx.restore();
}

/** Coupe un texte en lignes, avec des points de suspension au-delà de `maxLines`. */
function wrap(ctx: CanvasRenderingContext2D, text: string, maxWidth: number, maxLines: number) {
  const lines: string[] = [];
  let line = '';
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const candidate = line ? `${line} ${word}` : word;
    if (!line || ctx.measureText(candidate).width <= maxWidth) {
      line = candidate;
    } else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  const kept = lines.slice(0, maxLines);
  const last = kept.length - 1;
  if (last >= 0 && (lines.length > maxLines || ctx.measureText(kept[last]).width > maxWidth)) {
    let end = kept[last];
    while (end.length > 1 && ctx.measureText(`${end}…`).width > maxWidth) end = end.slice(0, -1);
    kept[last] = `${end.trimEnd()}…`;
  }
  return kept;
}

function sectionTitle(ctx: CanvasRenderingContext2D, p: Palette, text: string, y: number, line: string) {
  ctx.font = FONTS.heading(44);
  ctx.fillStyle = p.text;
  ctx.textBaseline = 'middle';
  ctx.fillText(text, MARGIN, y);
  ctx.strokeStyle = line;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(MARGIN + ctx.measureText(text).width + 24, y + 2);
  ctx.lineTo(WIDTH - MARGIN, y + 2);
  ctx.stroke();
  ctx.textBaseline = 'alphabetic';
}

function drawTalentStar(ctx: CanvasRenderingContext2D, p: Palette, x: number, y: number, size: number) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(size / 40, size / 40);
  ctx.beginPath();
  ctx.arc(20, 20, 18, 0, Math.PI * 2);
  ctx.fillStyle = p.talent;
  ctx.fill();
  ctx.lineWidth = 2.5;
  ctx.strokeStyle = p.accent;
  ctx.stroke();
  const star = new Path2D(TALENT_STAR);
  ctx.fillStyle = p.talentStar;
  ctx.fill(star);
  ctx.lineWidth = 1.6;
  ctx.lineJoin = 'round';
  ctx.stroke(star);
  ctx.restore();
}

function drawSeal(
  ctx: CanvasRenderingContext2D,
  p: Palette,
  x: number,
  y: number,
  size: number,
  known: boolean,
  fill = p.accentSoft,
) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(size / 80, size / 80);
  const edge = new Path2D(sealPath());
  if (known) {
    ctx.fillStyle = fill;
    ctx.fill(edge);
  }
  ctx.lineWidth = 1.8;
  ctx.strokeStyle = known ? p.text : p.textMuted;
  ctx.setLineDash(known ? [] : [3, 3]);
  ctx.stroke(edge);
  ctx.setLineDash([0.1, 4]);
  ctx.lineCap = 'round';
  ctx.strokeStyle = fill === p.accent ? p.onAccent : p.accent;
  ctx.beginPath();
  ctx.arc(40, 40, 28, 0, Math.PI * 2);
  ctx.stroke();
  ctx.restore();
}

async function loadFonts() {
  if (!document.fonts) return;
  const fonts = [FONTS.heading(40), FONTS.heading(40, 700), FONTS.body(30), FONTS.body(26, 400), FONTS.mono(22), FONTS.mono(22, 400)];
  await Promise.all(fonts.map((font) => document.fonts.load(font).catch(() => undefined)));
}

function drawPaper(ctx: CanvasRenderingContext2D, p: Palette, height: number) {
  ctx.fillStyle = p.bg;
  ctx.fillRect(0, 0, WIDTH, height);
  ctx.fillStyle = p.paper;
  ctx.strokeStyle = p.border;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(36, 36, WIDTH - 72, height - 72, 28);
  ctx.fill();
  ctx.stroke();
  ctx.strokeStyle = p.softLine;
  ctx.beginPath();
  ctx.roundRect(50, 50, WIDTH - 100, height - 100, 18);
  ctx.stroke();
  for (const [x, y, sx, sy] of [
    [62, 62, 1, 1],
    [WIDTH - 62, 62, -1, 1],
    [62, height - 62, 1, -1],
    [WIDTH - 62, height - 62, -1, -1],
  ]) {
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(sx * 1.6, sy * 1.6);
    drawPaths(ctx, CORNER, 0, 0, 1, p.accent, 1.4);
    ctx.restore();
  }
}

/** Même badge que ArchetypeBadge : double anneau abricot, médaillon crème, emoji ou « ? ». */
function drawArchetypeBadge(
  ctx: CanvasRenderingContext2D,
  p: Palette,
  cx: number,
  cy: number,
  radius: number,
  archetype: Archetype | null,
) {
  const ring = archetype ? p.peach : p.border;
  const circle = (r: number) => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
  };
  ctx.save();
  circle(radius);
  ctx.fillStyle = ring;
  ctx.fill();
  ctx.lineWidth = radius * 0.028;
  ctx.strokeStyle = p.text;
  ctx.stroke();
  const inner = radius * 0.85;
  circle(inner);
  ctx.fillStyle = p.medal;
  ctx.fill();
  circle(inner - radius * 0.09 - radius * 0.022);
  ctx.lineWidth = radius * 0.044;
  ctx.strokeStyle = ring;
  if (!archetype) ctx.setLineDash([radius * 0.08, radius * 0.06]);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  if (archetype) {
    ctx.font = FONTS.emoji(Math.round(radius * 0.88));
    ctx.fillStyle = p.text;
    ctx.fillText(archetype.emoji, cx, cy + radius * 0.04);
  } else {
    ctx.font = FONTS.heading(Math.round(radius * 0.8));
    ctx.fillStyle = p.onMedal;
    ctx.fillText('?', cx, cy + radius * 0.06);
  }
  ctx.restore();
}

const QUALITY_FONT = FONTS.body(22, 600);

function qualityWidth(ctx: CanvasRenderingContext2D, text: string) {
  ctx.save();
  ctx.font = QUALITY_FONT;
  const width = ctx.measureText(text).width + 32;
  ctx.restore();
  return width;
}

/** Pastille de la qualité de l'archétype (« Sociable »), posée sur la ligne de base du nom. */
function drawQuality(ctx: CanvasRenderingContext2D, p: Palette, text: string, x: number, baseline: number) {
  const width = qualityWidth(ctx, text);
  ctx.save();
  ctx.font = QUALITY_FONT;
  ctx.fillStyle = p.accentSoft;
  ctx.strokeStyle = p.accent;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(x, baseline - 28, width, 38, 19);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = p.accentText;
  ctx.fillText(text, x + 16, baseline - 1);
  ctx.restore();
}

function drawHeader(ctx: CanvasRenderingContext2D, p: Palette, sheet: CharacterSheet) {
  const { archetype } = sheet.identity;
  drawArchetypeBadge(ctx, p, MARGIN + 86, 216, 86, archetype);

  const x = 300;
  const width = WIDTH - MARGIN - x;
  ctx.font = FONTS.mono(22);
  ctx.fillStyle = p.accentText;
  ctx.fillText(sheetFr.hero.kicker.toUpperCase(), x, 158);
  ctx.font = FONTS.heading(88);
  ctx.fillStyle = p.text;
  ctx.fillText(wrap(ctx, sheet.identity.display_name, width, 1)[0], x, 244);
  // « ARCHÉTYPE » en petites capitales, puis le nom et sa qualité, comme sur la fiche.
  const gap = 18;
  const label = sheetFr.hero.archetype.toUpperCase();
  ctx.font = FONTS.mono(20);
  ctx.fillStyle = p.textMuted;
  ctx.fillText(label, x, 298);
  const nameX = x + ctx.measureText(label).width + gap;
  ctx.font = FONTS.heading(38, 700);
  ctx.fillStyle = p.text;
  if (archetype) {
    const room = WIDTH - MARGIN - nameX - qualityWidth(ctx, archetype.quality) - gap;
    const name = wrap(ctx, typo(archetype.name), room, 1)[0];
    ctx.fillText(name, nameX, 300);
    drawQuality(ctx, p, archetype.quality, nameX + ctx.measureText(name).width + gap, 300);
  } else {
    ctx.fillText(sheetFr.hero.noArchetype, nameX, 300);
  }
  ctx.font = FONTS.body(27, 400);
  ctx.fillStyle = p.textMuted;
  const motto = archetype ? quote(typo(archetype.motto)) : sheetFr.hero.noArchetypeHint;
  wrap(ctx, motto, width, 2).forEach((text, index) => ctx.fillText(text, x, 344 + index * 36));
}

function drawLevel(ctx: CanvasRenderingContext2D, p: Palette, sheet: CharacterSheet, top: number) {
  const { xp, level, level_title: title, level_xp: floor, next_level_xp: next } = sheet.progress;
  drawSeal(ctx, p, MARGIN, top, 124, true, p.accent);
  ctx.textAlign = 'center';
  ctx.fillStyle = p.onAccent;
  ctx.font = FONTS.mono(18);
  ctx.fillText(sheetFr.hero.level.toUpperCase(), MARGIN + 62, top + 50);
  ctx.font = FONTS.mono(48);
  ctx.fillText(String(level), MARGIN + 62, top + 96);
  ctx.textAlign = 'left';

  const x = MARGIN + 160;
  const width = WIDTH - MARGIN - x;
  ctx.fillStyle = p.text;
  ctx.font = FONTS.heading(44);
  ctx.fillText(typo(title), x, top + 46);
  ctx.fillStyle = p.surface;
  ctx.strokeStyle = p.line;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(x, top + 64, width, 24, 12);
  ctx.fill();
  ctx.stroke();
  const ratio = Math.min(1, Math.max(0, (xp - floor) / Math.max(1, next - floor)));
  if (ratio > 0) {
    ctx.fillStyle = p.accent;
    ctx.beginPath();
    ctx.roundRect(x + 2, top + 66, Math.max(20, (width - 4) * ratio), 20, 10);
    ctx.fill();
  }
  ctx.font = FONTS.mono(22, 400);
  ctx.fillStyle = p.textMuted;
  ctx.fillText(sheetFr.hero.xp(xp, next), x, top + 122);
}

function drawTalents(ctx: CanvasRenderingContext2D, p: Palette, sheet: CharacterSheet, top: number) {
  sectionTitle(ctx, p, sheetFr.talents.title, top, p.talent);
  let y = top + 44;
  const talents = sheet.talents.validated;
  if (talents.length === 0) {
    ctx.font = FONTS.body(26, 400);
    ctx.fillStyle = p.textMuted;
    for (const text of wrap(ctx, sheetFr.talents.empty, INNER, 3)) {
      ctx.fillText(text, MARGIN, y + 30);
      y += 36;
    }
    return;
  }
  for (const talent of talents.slice(0, MAX_TALENTS)) {
    ctx.fillStyle = p.talentSoft;
    ctx.strokeStyle = p.talent;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(MARGIN, y, INNER, 84, 20);
    ctx.fill();
    ctx.stroke();
    drawTalentStar(ctx, p, MARGIN + 18, y + 16, 52);
    ctx.fillStyle = p.text;
    ctx.font = FONTS.heading(32, 700);
    ctx.fillText(wrap(ctx, talent.name, INNER - 110, 1)[0], MARGIN + 90, y + 41);
    ctx.font = FONTS.mono(19);
    ctx.fillStyle = p.talentText;
    ctx.fillText((fr.map.categories[talent.category] ?? talent.category).toUpperCase(), MARGIN + 90, y + 68);
    y += 96;
  }
  if (talents.length > MAX_TALENTS) {
    const more = talents.length - MAX_TALENTS;
    ctx.font = FONTS.body(26);
    ctx.fillStyle = p.talentText;
    ctx.fillText(`+ ${more} ${more > 1 ? 'autres talents' : 'autre talent'}`, MARGIN, y + 22);
  }
}

function drawFacts(ctx: CanvasRenderingContext2D, p: Palette, facts: GameFact[], top: number) {
  sectionTitle(ctx, p, sheetFr.identity.title, top, p.line);
  const gap = 48;
  const width = (INNER - gap) / 2;
  facts.forEach((fact, index) => {
    const x = MARGIN + (index % 2) * (width + gap);
    const y = top + 30 + Math.floor(index / 2) * 80;
    ctx.font = FONTS.mono(19);
    ctx.fillStyle = p.textMuted;
    ctx.fillText(wrap(ctx, fact.label.toUpperCase(), width, 1)[0], x, y + 24);
    const color = isColorFact(fact) ? swatchFor(fact.value) : null;
    let valueX = x;
    if (color) {
      ctx.beginPath();
      ctx.arc(x + 12, y + 50, 11, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = p.text;
      ctx.stroke();
      valueX += 34;
    }
    ctx.font = FONTS.body(29);
    ctx.fillStyle = p.text;
    ctx.fillText(wrap(ctx, fact.value, width - (valueX - x), 1)[0], valueX, y + 60);
    ctx.strokeStyle = p.line;
    ctx.lineWidth = 2;
    ctx.setLineDash([2, 6]);
    ctx.beginPath();
    ctx.moveTo(x, y + 74);
    ctx.lineTo(x + width, y + 74);
    ctx.stroke();
    ctx.setLineDash([]);
  });
}

function drawAttributes(ctx: CanvasRenderingContext2D, p: Palette, sheet: CharacterSheet, top: number) {
  sectionTitle(ctx, p, sheetFr.attributes.title, top, p.line);
  const cell = INNER / Math.max(1, sheet.attributes.length);
  sheet.attributes.forEach((attribute, index) => {
    const centerX = MARGIN + cell * index + cell / 2;
    const y = top + 40;
    const known = attribute.score !== null;
    drawSeal(ctx, p, centerX - 54, y, 108, known);
    drawPaths(ctx, glyphFor(attribute.icon), centerX - 11.5, y + 20, 0.96, known ? p.accentText : p.textMuted);
    ctx.textAlign = 'center';
    ctx.fillStyle = known ? p.text : p.textMuted;
    ctx.font = known ? FONTS.mono(38) : FONTS.heading(40);
    ctx.fillText(known ? String(attribute.score) : '?', centerX, y + 86);
    ctx.fillStyle = p.text;
    ctx.font = FONTS.heading(26, 700);
    ctx.fillText(typo(attribute.label), centerX, y + 146);
    ctx.textAlign = 'left';
  });
}

/** Place les sections les unes sous les autres ; l'image s'allonge seulement si la fiche est riche. */
function layout(sheet: CharacterSheet) {
  const facts = orderFacts(sheet.facts)
    .filter((fact) => !fact.hidden)
    .slice(0, MAX_FACTS);
  const talents = sheet.talents.validated.length;
  const talentsHeight =
    44 + (talents ? Math.min(talents, MAX_TALENTS) * 96 + (talents > MAX_TALENTS ? 44 : 0) : 128);
  const talentsTop = 660;
  const factsTop = talentsTop + talentsHeight + SECTION_GAP;
  const attributesTop = facts.length ? factsTop + 30 + Math.ceil(facts.length / 2) * 80 + SECTION_GAP : factsTop;
  return { facts, talentsTop, factsTop, attributesTop, height: Math.max(MIN_HEIGHT, attributesTop + 332) };
}

export async function renderSheetPng(sheet: CharacterSheet): Promise<Blob> {
  await loadFonts();
  const plan = layout(sheet);
  const canvas = document.createElement('canvas');
  canvas.width = WIDTH;
  canvas.height = plan.height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('canvas');
  const p = readPalette();

  drawPaper(ctx, p, plan.height);
  drawHeader(ctx, p, sheet);
  drawLevel(ctx, p, sheet, 440);
  drawTalents(ctx, p, sheet, plan.talentsTop);
  if (plan.facts.length) drawFacts(ctx, p, plan.facts, plan.factsTop);
  drawAttributes(ctx, p, sheet, plan.attributesTop);

  ctx.font = FONTS.heading(26, 700);
  ctx.fillStyle = p.textMuted;
  ctx.textAlign = 'center';
  ctx.fillText(`${fr.appName} · ${sheetFr.hero.kicker}`, WIDTH / 2, plan.height - 76);

  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('png'))), 'image/png'),
  );
}

/** Nom de fichier sans accents ni espaces. */
export function fileSlug(name: string) {
  const slug = name
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
  return slug || 'aventure';
}
