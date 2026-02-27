import React, { useState, useEffect } from 'react';
import { ThemeContext } from './ThemeContextValue';

// The provider component is the only export from this file now, which
// keeps the module "component-only" for Fast Refresh.

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(
    typeof localStorage !== 'undefined'
      ? localStorage.getItem('theme') || 'dark'
      : 'dark'
  );

  useEffect(() => {
    const root = window.document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
