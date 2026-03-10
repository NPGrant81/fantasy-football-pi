import { execSync } from 'node:child_process';

const targetPath = 'cypress/screenshots/uat_capture_pages.spec.js';

function run(command) {
  return execSync(command, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
}

try {
  const changed = run(`git status --porcelain -- ${targetPath}`);

  if (!changed) {
    console.log('Visual regression check passed: screenshot baseline is unchanged.');
    process.exit(0);
  }

  console.error('Visual regression detected. Baseline screenshot diff found:');
  console.error(changed);
  process.exit(1);
} catch (error) {
  console.error('Unable to evaluate visual regression status.');
  console.error(error.message || error);
  process.exit(1);
}
