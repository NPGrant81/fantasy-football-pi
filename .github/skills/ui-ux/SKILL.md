---
name: ui-ux
description: 'Tailwind CSS light-first theming, dark mode conventions, component token system, responsive design, accessibility, and React component patterns for Fantasy Football PI. Use when: styling components, implementing dark mode, building responsive layouts, asking about UI tokens, adding new UI components, or reviewing visual design.'
argument-hint: 'Optional: focus area (theming | tokens | responsive | accessibility | components | dark-mode)'
---

# UI / UX

## Why This Exists
Fantasy Football PI uses a **light-first Tailwind CSS convention** that differs from the industry default of dark-first. Every component must support both modes through explicit `dark:` overrides. This skill prevents dark-only regressions and documents the token system that makes the UI consistent.

## Light-First Convention
**Light colors are the default; dark mode is an explicit override.**

```jsx
// ✅ Correct — light first, dark: override
<div className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100">

// ❌ Wrong — dark-only, no light mode
<div className="bg-slate-900 text-slate-100">

// ❌ Wrong — missing text color
<div className="bg-white dark:bg-slate-900">
```

**Rule**: If you write a `bg-` class, you must pair it with a `dark:bg-` class. Same for `text-`, `border-`, and `ring-`.

## Token System (from `frontend/src/utils/uiStandards.js`)

| Token | Light | Dark | Use For |
|-------|-------|------|---------|
| `cardSurface` | `bg-white border-slate-200` | `dark:bg-slate-900/30 dark:border-slate-700` | Cards, panels |
| `buttonPrimary` | `bg-indigo-600 text-white hover:bg-indigo-700` | same | Primary CTA |
| `buttonSecondary` | `bg-white text-slate-700 border-slate-300` | `dark:bg-slate-800 dark:text-slate-200` | Secondary action |
| `inputBase` | `bg-white border-slate-300 text-slate-900` | `dark:bg-slate-800 dark:border-slate-600 dark:text-slate-100` | Form inputs |
| `textMuted` | `text-slate-600` | `dark:text-slate-400` | Secondary text |
| `layerDrawer` | `bg-white` | `dark:bg-slate-800` | Sidebars, drawers |
| `modalOverlay` | `bg-black/50` | same | Modal backdrop |
| `modalSurface` | `bg-white` | `dark:bg-slate-900` | Modal container |
| `modalTitle` | `text-slate-900` | `dark:text-slate-100` | Modal headings |
| `modalCloseButton` | `text-slate-500 hover:text-slate-700` | `dark:text-slate-400 dark:hover:text-white` | Close (×) button |

## Common Patterns

### Card
```jsx
<div className="bg-white dark:bg-slate-900/30 rounded-lg border border-slate-200 dark:border-slate-700 p-4">
```

### Page section heading
```jsx
<h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">
```

### Muted/secondary text
```jsx
<p className="text-sm text-slate-600 dark:text-slate-400">
```

### Primary button
```jsx
<button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-medium transition-colors">
```

### Secondary/ghost button
```jsx
<button className="px-4 py-2 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
```

### Badge/pill
```jsx
<span className="px-2 py-0.5 text-xs rounded font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300">
```

### Form input
```jsx
<input className="w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
```

## Position Badge Colors
Used consistently in analytics and player views:
```jsx
const POSITION_COLORS = {
  QB: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300',
  RB: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  WR: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  TE: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  K:  'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300',
};
```

## Responsive Guidelines
- Mobile-first layout with `sm:`, `md:`, `lg:` breakpoints
- Two-column layouts: `grid grid-cols-1 lg:grid-cols-2 gap-4`
- Tables: wrap in `overflow-x-auto` for horizontal scroll on mobile
- Fixed-width sidebars: use `sticky top-0` for scroll persistence
- See `RESPONSIVE_STANDARDS.md` for full breakpoint matrix

## React Component Rules
- **Functional components only** — no class components
- **PascalCase filenames**: `PlayerConsistencyChart.jsx`
- **No custom CSS files** — Tailwind only; exception: complex animations in `index.css`
- **Lazy load large pages**: `const Analytics = React.lazy(() => import('./pages/Analytics'))`
- **Context for shared state**: follow `ThemeContext` pattern
- **No Redux/Zustand** — React Context is the state management solution

## Loading/Error States
Use shared `AsyncState` components:
```jsx
import { LoadingState, ErrorState } from '@components/common/AsyncState';

if (loading) return <LoadingState message="Loading data..." className="h-96" />;
if (error) return <ErrorState message={error} />;
```

## Chart Components (Chart.js via react-chartjs-2)
Available: `Bar`, `Line`, `Scatter`, `Doughnut`
- Register required Chart.js components at the top of the file
- Use `AspectRatio` / `maintainAspectRatio` for responsive sizing
- Custom tooltip `backgroundColor`: `'rgba(0, 0, 0, 0.8)'`
- No Plotly — `react-plotly.js` is not in the dependency list

## Accessibility Checklist
- All interactive elements must be keyboard focusable
- Use semantic HTML: `<button>` not `<div onClick>`
- Include `title` attributes on icon-only buttons
- Maintain color contrast: muted text uses `text-slate-600` (4.5:1 on white)
- Form labels must be explicitly associated with inputs via `htmlFor` / `id`

## Always Do
- Light colors first, `dark:` overrides second — every single class pair
- Use `transition-colors` on interactive elements
- Use `rounded` for cards; `rounded-lg` for larger containers
- Test in both light and dark mode before committing
- Use `truncate` + `max-w-*` for player names in tight spaces
- Run `check-ui.js` to audit for dark-only class regressions: `node check-ui.js`

## Never Do
- Never write a dark-only class without a light counterpart
- Never use inline `style={{}}` for colors — Tailwind only
- Never create a `.css` file for component styles
- Never use `!important` in Tailwind (`!` prefix) unless fixing a third-party conflict
- Never use class-based React components

## Related Skills
- [Testing](../testing/SKILL.md) — component test patterns
- [Architecture](../architecture/SKILL.md) — frontend layer conventions
- [Token Reference](./references/token-reference.md) — complete token listing
