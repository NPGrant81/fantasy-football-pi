import { useContext } from 'react';
import { ThemeContext } from '@/context/ThemeContextValue';

export function useTheme() {
  return useContext(ThemeContext);
}
