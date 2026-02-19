import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

const ports = [
  process.env.E2E_PORT,
  '5173',
  '5174',
  '4173'
].filter(Boolean);

const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const useShell = process.platform === 'win32';
const waitMs = Number(process.env.E2E_WAIT_MS || 60000);
const pollMs = 500;

async function waitForServer(url, timeoutMs, isDevAlive) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (!isDevAlive()) {
      return false;
    }

    try {
      const response = await fetch(url, { method: 'GET' });
      if (response.ok) {
        return true;
      }
    } catch {
      // Keep polling until the server responds or times out.
    }

    await delay(pollMs);
  }

  return false;
}

async function runForPort(port) {
  const baseUrl = `http://localhost:${port}`;
  const devArgs = ['run', 'dev', '--', '--port', String(port), '--strictPort'];

  const devProcess = spawn(npmCmd, devArgs, { stdio: 'inherit', shell: useShell });
  let devExited = false;
  devProcess.on('exit', () => {
    devExited = true;
  });

  const ready = await waitForServer(baseUrl, waitMs, () => !devExited);
  if (!ready) {
    if (!devExited) {
      devProcess.kill();
    }
    return { ok: false, baseUrl };
  }

  const cypressArgs = ['run', 'e2e:run'];
  const cypressEnv = { ...process.env, CYPRESS_BASE_URL: baseUrl };
  const cypressProcess = spawn(npmCmd, cypressArgs, { 
    stdio: 'inherit', 
    shell: useShell,
    env: cypressEnv 
  });

  const exitCode = await new Promise((resolve) => {
    cypressProcess.on('exit', resolve);
  });

  devProcess.kill();
  return { ok: exitCode === 0, baseUrl, exitCode };
}

(async () => {
  for (const port of ports) {
    const result = await runForPort(port);
    if (result.ok) {
      process.exit(0);
    }
  }

  console.error('E2E failed: dev server did not become ready on any port.');
  process.exit(1);
})();
