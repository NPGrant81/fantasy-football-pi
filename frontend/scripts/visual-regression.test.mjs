import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { compareVisualBaselines } from './visual-regression.mjs';
import { PNG } from 'pngjs';

async function createFixtureDirectories() {
  const root = await mkdtemp(path.join(os.tmpdir(), 'ffpi-visual-regression-'));
  const baselineDirectory = path.join(root, 'baseline');
  const actualDirectory = path.join(root, 'actual');
  const diffDirectory = path.join(root, 'diff');
  await Promise.all([
    mkdir(baselineDirectory),
    mkdir(actualDirectory),
    mkdir(diffDirectory),
  ]);
  return { root, baselineDirectory, actualDirectory, diffDirectory };
}

function solidImage(color, width = 10, height = 10) {
  const image = new PNG({ width, height });
  for (let offset = 0; offset < image.data.length; offset += 4) {
    image.data.set([...color, 255], offset);
  }
  return image;
}

async function writeImage(directory, filename, image) {
  await writeFile(path.join(directory, filename), PNG.sync.write(image));
}

test('identical screenshots pass without producing diff images', async (t) => {
  const fixture = await createFixtureDirectories();
  t.after(() => rm(fixture.root, { recursive: true, force: true }));
  const image = solidImage([255, 255, 255]);
  await writeImage(fixture.baselineDirectory, 'page.png', image);
  await writeImage(fixture.actualDirectory, 'page.png', image);

  const result = await compareVisualBaselines(fixture);

  assert.equal(result.compared, 1);
  assert.deepEqual(result.failures, []);
  assert.deepEqual(await readdir(fixture.diffDirectory), []);
});

test('changed screenshots fail and produce a reviewable diff image', async (t) => {
  const fixture = await createFixtureDirectories();
  t.after(() => rm(fixture.root, { recursive: true, force: true }));
  const baseline = solidImage([255, 255, 255]);
  const actual = solidImage([255, 255, 255]);
  actual.data.set([0, 0, 0, 255], 0);
  await writeImage(fixture.baselineDirectory, 'page.png', baseline);
  await writeImage(fixture.actualDirectory, 'page.png', actual);

  const result = await compareVisualBaselines(fixture);

  assert.equal(result.compared, 1);
  assert.equal(result.failures.length, 1);
  assert.match(result.failures[0].reason, /pixels differ/);
  const diffImage = PNG.sync.read(
    await readFile(path.join(fixture.diffDirectory, 'page.diff.png')),
  );
  assert.equal(diffImage.width, 10);
  assert.equal(diffImage.height, 10);
});

test('missing baselines and screenshots fail explicitly', async (t) => {
  const fixture = await createFixtureDirectories();
  t.after(() => rm(fixture.root, { recursive: true, force: true }));
  await writeImage(
    fixture.baselineDirectory,
    'missing-actual.png',
    solidImage([255, 255, 255]),
  );
  await writeImage(
    fixture.actualDirectory,
    'missing-baseline.png',
    solidImage([255, 255, 255]),
  );

  const result = await compareVisualBaselines(fixture);

  assert.deepEqual(result.failures, [
    { filename: 'missing-actual.png', reason: 'screenshot is missing' },
    { filename: 'missing-baseline.png', reason: 'baseline is missing' },
  ]);
});

test('changed screenshot dimensions fail explicitly', async (t) => {
  const fixture = await createFixtureDirectories();
  t.after(() => rm(fixture.root, { recursive: true, force: true }));
  await writeImage(
    fixture.baselineDirectory,
    'page.png',
    new PNG({ width: 10, height: 10 }),
  );
  await writeImage(
    fixture.actualDirectory,
    'page.png',
    new PNG({ width: 11, height: 10 }),
  );

  const result = await compareVisualBaselines(fixture);

  assert.equal(result.failures.length, 1);
  assert.match(result.failures[0].reason, /dimensions changed/);
  const diffImage = PNG.sync.read(
    await readFile(path.join(fixture.diffDirectory, 'page.diff.png')),
  );
  assert.equal(diffImage.width, 11);
  assert.equal(diffImage.height, 10);
});
