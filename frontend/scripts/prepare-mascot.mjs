/**
 * Prépare Néo pour le web à partir de mascotte/neo.glb :
 * géométrie et animations compressées, textures en WebP, noms des clips conservés.
 *
 * Usage : npm run mascot
 * ./run.sh le relance tout seul quand mascotte/neo.glb est plus récent.
 */
import { mkdir, stat } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, meshopt, prune, resample, textureCompress } from '@gltf-transform/functions';
import { MeshoptDecoder, MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(root, process.argv[2] ?? '../mascotte/neo.glb');
const target = resolve(root, 'src/mascot/neo.glb');
const TEXTURE_SIZE = 1024;
const NORMAL_MAP_SIZE = 512;

await MeshoptEncoder.ready;
await MeshoptDecoder.ready;

const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ 'meshopt.decoder': MeshoptDecoder, 'meshopt.encoder': MeshoptEncoder });

const document = await io.read(source);
await document.transform(
  dedup(),
  resample(),
  // Les os et accessoires sans géométrie servent aux animations : on les garde.
  prune({ keepLeaves: true, keepAttributes: true, keepIndices: true, keepExtras: true }),
  textureCompress({
    encoder: sharp,
    targetFormat: 'webp',
    slots: /^(?!normalTexture)/,
    resize: [TEXTURE_SIZE, TEXTURE_SIZE],
    quality: 82,
  }),
  textureCompress({
    encoder: sharp,
    targetFormat: 'webp',
    slots: /^normalTexture/,
    resize: [NORMAL_MAP_SIZE, NORMAL_MAP_SIZE],
    quality: 80,
  }),
  meshopt({ encoder: MeshoptEncoder, level: 'medium' }),
);

await mkdir(dirname(target), { recursive: true });
await io.write(target, document);

const clips = document.getRoot().listAnimations().map((clip) => clip.getName());
const [before, after] = await Promise.all([stat(source), stat(target)]);
const megabytes = (bytes) => `${(bytes / 1e6).toFixed(2)} Mo`;
console.log(`Néo : ${megabytes(before.size)} → ${megabytes(after.size)}, ${clips.length} clips`);
console.log(clips.join(', '));
