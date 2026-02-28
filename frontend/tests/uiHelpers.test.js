import {
  isDarkTheme,
  setDocumentTheme,
  toggleDocumentTheme,
} from '../src/utils/uiHelpers';

// these helpers operate directly on document.documentElement

describe('uiHelpers theme functions', () => {
  beforeEach(() => {
    // ensure clean state
    document.documentElement.classList.remove('dark');
  });

  it('isDarkTheme returns false when no class present', () => {
    expect(isDarkTheme()).toBe(false);
  });

  it('setDocumentTheme("dark") adds class and isDarkTheme true', () => {
    setDocumentTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(isDarkTheme()).toBe(true);
  });

  it('setDocumentTheme("light") removes class', () => {
    document.documentElement.classList.add('dark');
    setDocumentTheme('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('toggleDocumentTheme flips the class', () => {
    expect(isDarkTheme()).toBe(false);
    toggleDocumentTheme();
    expect(isDarkTheme()).toBe(true);
    toggleDocumentTheme();
    expect(isDarkTheme()).toBe(false);
  });
});
