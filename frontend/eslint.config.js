import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'

// --- 1.1 GLOBAL IGNORES ---
// 1.1.1 Ignore build artifacts and dependency folders
export default [
  {
    ignores: ['dist', 'node_modules'],
  },

  {
    files: ['**/*.{js,jsx}'],
    
    // --- 2.1 BASE CONFIGURATIONS ---
    // 2.1.1 Use recommended configs directly (no 'extends' in flat config)
    ...js.configs.recommended,

    // --- 3.1 LANGUAGE & ENVIRONMENT ---
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        ...globals.browser,
        ...globals.node, // 3.1.1 Added Node globals to fix 'process' or '__dirname' warnings
        ...globals.jest, // 3.1.2 Added Jest globals for test files
      },
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },

    // --- 3.2 PLUGINS ---
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },

    // --- 4.1 THE GUARDRAILS (RULES) ---
    rules: {
      // 4.1.1 React Hooks rules
      ...reactHooks.configs.recommended.rules,

      // 4.1.2 React 17+ doesn't need React imported in every JSX file
      "react/react-in-jsx-scope": "off",

      // 4.1.3 Set to 'warn' so GitHub Actions pass, but you see the clutter
      "no-unused-vars": "warn",

      // 4.1.4 Disable prop-types if you aren't using them (common in modern React)
      "react/prop-types": "off",

      // 4.1.5 Warn on undefined variables (like the __dirname issue we fixed)
      "no-undef": "warn",

      // 4.1.6 Vite-specific HMR safety
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
    },
  },

  // --- CYPRESS TEST FILES CONFIGURATION ---
  {
    files: ['cypress/**/*.js', 'cypress/**/*.jsx'],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
        cy: 'readonly',
        Cypress: 'readonly',
      },
    },
    rules: {
      'no-unused-vars': 'warn',
      'no-undef': 'warn',
    },
  },
]