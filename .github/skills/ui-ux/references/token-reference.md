# UI Token Reference — Fantasy Football PI

Complete listing of all Tailwind token patterns. Use these exact class combinations for consistency.

## Surfaces

| Token Name | Light classes | Dark classes |
|-----------|---------------|--------------|
| Page background | `bg-slate-50` | `dark:bg-slate-950` |
| Card surface | `bg-white border border-slate-200` | `dark:bg-slate-900/30 dark:border-slate-700` |
| Elevated card | `bg-white shadow-sm border border-slate-200` | `dark:bg-slate-900 dark:border-slate-700` |
| Drawer / sidebar | `bg-white border-r border-slate-200` | `dark:bg-slate-800 dark:border-slate-700` |
| Modal overlay | `bg-black/50` | same |
| Modal container | `bg-white rounded-xl shadow-2xl` | `dark:bg-slate-900` |
| Table row (even) | `bg-white` | `dark:bg-slate-900` |
| Table row (odd) | `bg-slate-50/40` | `dark:bg-slate-800/20` |
| Table header | `bg-slate-50` | `dark:bg-slate-800` |

## Text

| Token Name | Light | Dark |
|-----------|-------|------|
| Primary text | `text-slate-900` | `dark:text-slate-100` |
| Secondary text | `text-slate-700` | `dark:text-slate-300` |
| Muted text | `text-slate-600` | `dark:text-slate-400` |
| Placeholder | `placeholder-slate-400` | `dark:placeholder-slate-500` |
| Label | `text-slate-700 font-medium` | `dark:text-slate-300` |
| Heading (page) | `text-2xl font-bold text-slate-900` | `dark:text-slate-100` |
| Heading (section) | `text-lg font-semibold text-slate-900` | `dark:text-slate-100` |
| Heading (card) | `text-sm font-semibold text-slate-900` | `dark:text-slate-100` |

## Interactive Elements

| Token Name | Full class string |
|-----------|-------------------|
| Button primary | `px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded font-medium transition-colors` |
| Button secondary | `px-4 py-2 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border border-slate-300 dark:border-slate-600 rounded hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors` |
| Button danger | `px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded font-medium transition-colors` |
| Button ghost | `px-3 py-1.5 text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition-colors` |
| Icon button (close) | `text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-white p-1 rounded transition-colors` |
| Tab (active) | `border-b-2 border-indigo-600 text-indigo-600 dark:text-indigo-400 font-medium` |
| Tab (inactive) | `border-b-2 border-transparent text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100` |

## Form Elements

| Element | Full class string |
|---------|-------------------|
| Text input | `w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500` |
| Select | `w-full px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500` |
| Checkbox | `h-4 w-4 rounded border-slate-400 bg-white dark:border-slate-600 dark:bg-slate-800 text-indigo-600 focus:ring-indigo-500` |
| Label | `text-sm font-medium text-slate-900 dark:text-slate-200` |

## Badges & Pills

| Type | Classes |
|------|---------|
| Neutral | `px-2 py-0.5 text-xs rounded bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300` |
| Primary | `px-2 py-0.5 text-xs rounded bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300` |
| Success | `px-2 py-0.5 text-xs rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300` |
| Warning | `px-2 py-0.5 text-xs rounded bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300` |
| Danger | `px-2 py-0.5 text-xs rounded bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300` |

## Position Colors

```jsx
const POSITION_COLORS = {
  QB: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300',
  RB: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  WR: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-300',
  TE: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
  K:  'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-300',
  DEF: 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-300',
};
```

## Borders & Dividers

| Use | Classes |
|-----|---------|
| Card border | `border border-slate-200 dark:border-slate-700` |
| Divider | `border-t border-slate-200 dark:border-slate-700` |
| Focused input ring | `focus:ring-2 focus:ring-indigo-500` |
| Danger border | `border border-red-300 dark:border-red-700` |

## Spacing Conventions

| Context | Padding |
|---------|---------|
| Card inner | `p-4` |
| Card inner (large) | `p-6` |
| Table cell | `p-2` or `px-3 py-2` |
| Button | `px-4 py-2` |
| Badge | `px-2 py-0.5` |
| Icon button | `p-1` or `p-2` |

## Dark Mode Audit Tool
Run to detect dark-only class regressions:
```bash
node check-ui.js
```
