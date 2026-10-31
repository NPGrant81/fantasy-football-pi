import { mkdir, readdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';

export const MAX_DIFF_RATIO = 0.001;
export const PIXEL_THRESHOLD = 0.1;

async function listPngFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith('.png'))
    .map((entry) => entry.name)
    .sort();
}

function padImage(image, width, height) {
  const padded = new PNG({ width, height });
  for (let row = 0; row < image.height; row += 1) {
    const sourceStart = row * image.width * 4;
    const targetStart = row * width * 4;
    image.data.copy(
      padded.data,
      targetStart,
      sourceStart,
      sourceStart + image.width * 4,
    );
  }
  return padded;
}

export async function compareVisualBaselines({
  baselineDirectory,
  actualDirectory,
  diffDirectory,
  maxDiffRatio = MAX_DIFF_RATIO,
}) {
  await rm(diffDirectory, { recursive: true, force: true });
  await mkdir(diffDirectory, { recursive: true });

  const baselineFiles = await listPngFiles(baselineDirectory);
  const actualFiles = await listPngFiles(actualDirectory);
  if (baselineFiles.length === 0) {
    throw new Error(`No PNG baselines found in ${baselineDirectory}`);
  }
  if (actualFiles.length === 0) {
    throw new Error(`No actual screenshots found in ${actualDirectory}`);
  }

  const baselineSet = new Set(baselineFiles);
  const actualSet = new Set(actualFiles);
  const failures = [];

  for (const filename of baselineFiles) {
    if (!actualSet.has(filename)) {
      failures.push({ filename, reason: 'screenshot is missing' });
    }
  }
  for (const filename of actualFiles) {
    if (!baselineSet.has(filename)) {
      failures.push({ filename, reason: 'baseline is missing' });
    }
  }

  let compared = 0;
  for (const filename of baselineFiles.filter((file) => actualSet.has(file))) {
    const baseline = PNG.sync.read(await readFile(path.join(baselineDirectory, filename)));
    const actual = PNG.sync.read(await readFile(path.join(actualDirectory, filename)));
    const width = Math.max(baseline.width, actual.width);
    const height = Math.max(baseline.height, actual.height);
    const alignedBaseline = padImage(baseline, width, height);
    const alignedActual = padImage(actual, width, height);
    const diff = new PNG({ width, height });
    const differentPixels = pixelmatch(
      alignedBaseline.data,
      alignedActual.data,
      diff.data,
      width,
      height,
      { threshold: PIXEL_THRESHOLD, includeAA: false },
    );
    const diffRatio = differentPixels / (width * height);
    const dimensionsChanged =
      baseline.width !== actual.width || baseline.height !== actual.height;
    compared += 1;

    if (differentPixels > 0) {
      await writeFile(
        path.join(diffDirectory, filename.replace(/\.png$/, '.diff.png')),
        PNG.sync.write(diff),
      );
    }

    if (dimensionsChanged || diffRatio > maxDiffRatio) {
      failures.push({
        filename,
        reason: dimensionsChanged
          ? `dimensions changed from ${baseline.width}x${baseline.height} to ${actual.width}x${actual.height}`
          : `${differentPixels} pixels differ (${(diffRatio * 100).toFixed(3)}%)`,
      });
    }
  }

  return { compared, failures };
}
