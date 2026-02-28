# UI Responsive Standards for Fantasy Football Pi

## 1. Global Breakpoint Strategy (Tailwind)

All components must use a **mobile–first** approach.

- **Mobile (Default):** Single column, stacked labels, full width.
- **Tablet (`md:`):** 2–3 columns, side‑by‑side labels where space permits.
- **Desktop (`lg:`/`xl:`):** 4+ columns (grid) or 10‑12 columns (Draft Board).

## 2. Text & Typography Scaling

- Headers should be `text-lg` on mobile and scale to `text-2xl` on `lg:`.
- Secondary stats (e.g. "Drafted | Remaining") must use `text-[10px]` or `text-xs` to prevent overflow on small screens.

## 3. Component‑Specific Rules

### Grid Layouts

Use responsive grid classes across the board:

```
grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-10
```

### Tables/Lists

Wrap tables in an `overflow-x-auto` container to ensure they don't break layout on mobile.

### Draft Board

- Mobile: 1‑column stacked cells.
- Tablet: 4‑column grid.
- Desktop: 10–12 column grid (`lg:grid-cols-10`).

## 4. Breakpoint Cheat Sheet (for AI)

| Element      | Mobile (default) | Tablet (`md:`) | Desktop (`lg:`) |
| ------------ | ---------------- | -------------- | --------------- |
| Draft grid   | `grid-cols-1`    | `grid-cols-4`  | `grid-cols-10`  |
| Team headers | `flex-col`       | `flex-col`     | `flex-row`      |
| Font size    | `text-xs`        | `text-sm`      | `text-base`     |
| Padding      | `p-2`            | `p-3`          | `p-4`           |

## 5. Global CSS Enforcer

You can add the following to `src/index.css` as a safety net:

```css
/* Global Breakpoint Enforcer */
@layer components {
  .responsive-grid-container {
    @apply grid gap-4 grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-10;
  }

  .responsive-stack {
    @apply flex flex-col lg:flex-row lg:items-center lg:justify-between;
  }
}
```

---

### Workflow Notes

1. **Audit script** (bash or node) can be used to find files lacking responsive prefixes.
2. **AI Prompt**: "Using the rules defined in `@RESPONSIVE_STANDARDS.md`, refactor all .jsx files in `/src/pages` and `/src/components` to include Tailwind responsive breakpoints."
3. After AI refactor run audit again to verify zero files reported.

This file serves as the source‑of‑truth for any automated refactoring tool and ensures consistent responsive behavior across the app.
