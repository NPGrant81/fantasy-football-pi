import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';

const SRC_DIR = path.resolve('src');
const EXTENSIONS = new Set(['.js', '.jsx', '.ts', '.tsx']);

// Intentional full-screen dark auth gate.
const FILE_ALLOWLIST = new Set([
  path.normalize('src/components/LeagueSelector.jsx'),
]);

function walk(dir) {
  const entries = readdirSync(dir);
  let files = [];

  for (const entry of entries) {
    const abs = path.join(dir, entry);
    const st = statSync(abs);
    if (st.isDirectory()) {
      files = files.concat(walk(abs));
      continue;
    }

    if (EXTENSIONS.has(path.extname(abs))) {
      files.push(abs);
    }
  }

  return files;
}

function collectClassStrings(source) {
  const results = [];
  const patterns = [
    /className\s*=\s*"([^"]*)"/g,
    /className\s*=\s*'([^']*)'/g,
    /className\s*=\s*\{\s*`([\s\S]*?)`\s*\}/g,
    /className\s*=\s*\{\s*"([^"]*)"\s*\}/g,
  ];

  for (const re of patterns) {
    let m;
    while ((m = re.exec(source)) !== null) {
      results.push({ value: m[1], index: m.index });
    }
  }

  return results;
}

function cleanToken(token) {
  return token.replace(/^[`'"{(]+|[`'"})!,;]+$/g, '');
}

function isDarkVariantToken(token) {
  return cleanToken(token).includes('dark:');
}

function getUtility(token) {
  const parts = cleanToken(token).split(':');
  return parts[parts.length - 1];
}

function isDarkNeutralBgUtility(utility) {
  return /^(?:bg)-(?:slate|gray|zinc|neutral|stone)-(?:8|9)\d{2}(?:\/\d+)?$/.test(utility);
}

function hasLightNeutralBg(tokens) {
  return tokens.some((token) => {
    if (isDarkVariantToken(token)) return false;
    const utility = getUtility(token);
    return /^(?:bg)-(?:white|slate-(?:50|100|200|300)|gray-(?:50|100|200|300)|zinc-(?:50|100|200|300)|neutral-(?:50|100|200|300)|stone-(?:50|100|200|300))(?:\/\d+)?$/.test(
      utility
    );
  });
}

function findLineNumber(source, index) {
  return source.slice(0, index).split('\n').length;
}

function main() {
  const files = walk(SRC_DIR);
  const violations = [];

  for (const absFile of files) {
    const relFile = path.normalize(path.relative(process.cwd(), absFile));
    if (FILE_ALLOWLIST.has(relFile)) continue;

    const source = readFileSync(absFile, 'utf8');
    const classStrings = collectClassStrings(source);

    for (const cls of classStrings) {
      const normalized = cls.value.replace(/\$\{[^}]*\}/g, ' ');
      const tokens = normalized.split(/\s+/).map((t) => t.trim()).filter(Boolean);
      const hasLight = hasLightNeutralBg(tokens);

      for (const token of tokens) {
        if (isDarkVariantToken(token)) continue;
        const utility = getUtility(token);
        if (!isDarkNeutralBgUtility(utility)) continue;

        const hasDarkCounterpart = tokens.some((candidate) => {
          const cleaned = cleanToken(candidate);
          return cleaned === `dark:${utility}` || cleaned.endsWith(`dark:${utility}`);
        });

        if (hasDarkCounterpart) continue;

        if (!hasLight) {
          violations.push({
            file: relFile,
            line: findLineNumber(source, cls.index),
            token,
            message:
              'Dark neutral background class used as base style without a light-mode base class.',
          });
        }
      }
    }
  }

  if (violations.length === 0) {
    console.log('Theme guardrails passed: no dark-first neutral background base classes found.');
    process.exit(0);
  }

  console.error('Theme guardrails failed. Please convert these to light-first + dark: overrides:');
  for (const v of violations) {
    console.error(`- ${v.file}:${v.line} -> ${v.token} (${v.message})`);
  }
  process.exit(1);
}

main();
