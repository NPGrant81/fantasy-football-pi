// Separate file containing just the context object so that
// ``ThemeContext.jsx`` can export only the provider component
// (satisfies Fast Refresh requirement).

import { createContext } from 'react';

export const ThemeContext = createContext({
  theme: 'dark',
  setTheme: () => {},
});
