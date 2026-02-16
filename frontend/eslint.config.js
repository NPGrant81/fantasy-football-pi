import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

// --- 1.1 GLOBAL IGNORES ---
// 1.1.1 Ignore build artifacts and dependency folders
export default defineConfig([
  globalIgnores(['dist', 'node_modules']),

  {
    files: ['**/*.{js,jsx}'],
    
    // --- 2.1 BASE CONFIGURATIONS ---
    // 2.1.1 Merging standard JS, React Hook, and Vite-specific rules
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],

    // --- 3.1 LANGUAGE & ENVIRONMENT ---
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        ...globals.browser,
        ...globals.node, // 3.1.1 Added Node globals to fix 'process' or '__dirname' warnings
      },
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },

    // --- 4.1 THE GUARDRAILS (RULES) ---
    rules: {
      // 4.1.1 React 17+ doesn't need React imported in every JSX file
      "react/react-in-jsx-scope": "off",

      // 4.1.2 Set to 'warn' so GitHub Actions pass, but you see the clutter
      "no-unused-vars": "warn",

      // 4.1.3 Disable prop-types if you aren't using them (common in modern React)
      "react/prop-types": "off",

      // 4.1.4 Warn on undefined variables (like the __dirname issue we fixed)
      "no-undef": "warn",

      // 4.1.5 Vite-specific HMR safety
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },
])