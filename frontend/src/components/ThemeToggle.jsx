import React from 'react';
import { FiSun, FiMoon } from 'react-icons/fi';
import { useTheme } from '../hooks/useTheme';

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  const isDark = theme === 'dark';

  return (
    <button
      aria-label="Toggle light / dark mode"
      onClick={() => setTheme(isDark ? 'light' : 'dark')}
      className="relative w-14 h-7 md:w-16 md:h-8 focus:outline-none"
    >
      {/* track */}
      <div
        className={
          'absolute inset-0 rounded-full transition-colors ' +
          (isDark ? 'bg-black' : 'bg-white border border-slate-400')
        }
      />

      {/* bubble with icon */}
      <div
        className={
          'absolute top-0.5 w-6 h-6 bg-white rounded-full shadow flex items-center justify-center transition-all ' +
          (isDark ? 'left-0.5' : 'right-0.5')
        }
      >
        {isDark ? (
          <FiMoon className="text-sm text-gray-800" />
        ) : (
          <FiSun className="text-sm text-yellow-400" />
        )}
      </div>
    </button>
  );
}
