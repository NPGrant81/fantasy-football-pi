/* ignore-breakpoints */
import React from 'react';
import {
  tableHead,
  tableRow,
  tableStateCell,
  tableSurface,
  textMuted,
} from '@utils/uiStandards';

export function StandardTableContainer({ children, className = '' }) {
  return <div className={`${tableSurface} ${className}`.trim()}>{children}</div>;
}

export function StandardTable({ children, className = '' }) {
  return (
    <table className={`w-full text-left text-sm text-slate-700 dark:text-slate-300 ${className}`.trim()}>
      {children}
    </table>
  );
}

export function StandardTableHead({ headers }) {
  return (
    <thead className={tableHead}>
      <tr>
        {headers.map((header) => (
          <th key={header.key} className={header.className || 'px-3 py-2'}>
            {header.label}
          </th>
        ))}
      </tr>
    </thead>
  );
}

export function StandardTableRow({ children, className = '' }) {
  return <tr className={`${tableRow} ${className}`.trim()}>{children}</tr>;
}

export function StandardTableStateRow({ colSpan, children }) {
  return (
    <tr>
      <td className={tableStateCell} colSpan={colSpan}>
        <span className={textMuted}>{children}</span>
      </td>
    </tr>
  );
}
