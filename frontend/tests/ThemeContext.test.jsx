import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '../src/context/ThemeContext';
import { useTheme } from '../src/hooks/useTheme';
import ThemeToggle from '../src/components/ThemeToggle';
import React from 'react';
import { vi } from 'vitest';

// helper to stub prefers-color-scheme
function mockMatchMedia(matches) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query) => ({
      matches,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
}

function Dummy() {
  const { theme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}>
        toggle
      </button>
    </div>
  );
}

describe('ThemeContext', () => {
  beforeEach(() => localStorage.clear());

  it('defaults to light when no system preference and updates document class', () => {
    render(
      <ThemeProvider>
        <Dummy />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('toggles theme and persists to localStorage', () => {
    render(
      <ThemeProvider>
        <Dummy />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByText('toggle'));
    expect(screen.getByTestId('theme').textContent).toBe('dark');
    expect(localStorage.getItem('theme')).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('uses system preference when no stored value exists', () => {
    mockMatchMedia(true); // pretend OS is dark
    render(
      <ThemeProvider>
        <Dummy />
      </ThemeProvider>
    );
    expect(screen.getByTestId('theme').textContent).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('ThemeToggle button displays correct icon and flips theme', () => {
    mockMatchMedia(false);
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>
    );
    const btn = screen.getByRole('button', { name: /toggle light/i });
    // initial should be light because matchMedia returns false
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    // clicking should flip to dark and button should still exist
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });
});
