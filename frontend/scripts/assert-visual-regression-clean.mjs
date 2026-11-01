import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compareVisualBaselines } from './visual-regression.mjs';

const frontendDirectory = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  '..',
);
const screenshotDirectory = path.join(
  frontendDirectory,
  'cypress',
  'screenshots',
  'uat_capture_pages.spec.js',
);
const baselineDirectory = path.join(
  frontendDirectory,
  'cypress',
  'visual-baselines',
  'uat_capture_pages.spec.js',
);
const diffDirectory = path.join(frontendDirectory, 'cypress', 'visual-diffs');

try {
  const { compared, failures } = await compareVisualBaselines({
    baselineDirectory,
    actualDirectory: screenshotDirectory,
    diffDirectory,
  });

  if (failures.length > 0) {
    console.error('Visual regression check failed:');
    for (const failure of failures) {
      console.error(`- ${failure.filename}: ${failure.reason}`);
    }
    console.error(`PNG diff images were written to ${diffDirectory}.`);
    process.exitCode = 1;
  } else {
    console.log(`Visual regression check passed for ${compared} screenshots.`);
  }
} catch (error) {
  console.error('Unable to compare visual regression baselines.');
  console.error(error.message || error);
  process.exitCode = 1;
}
