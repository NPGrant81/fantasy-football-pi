import { render, screen } from '@testing-library/react';
import { vi, describe, test, expect } from 'vitest';

vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg></svg>' }),
  },
}));

// Mock MermaidDiagram to keep MarkdownRenderer tests simple
vi.mock('../src/components/MermaidDiagram', () => ({
  default: ({ chart }) => <div data-testid="mermaid-diagram">{chart}</div>,
}));

import MarkdownRenderer from '../src/components/MarkdownRenderer';

describe('MarkdownRenderer', () => {
  test('renders plain markdown text', () => {
    render(<MarkdownRenderer>Hello **world**</MarkdownRenderer>);
    expect(screen.getByText(/Hello/)).toBeInTheDocument();
    expect(screen.getByText(/world/)).toBeInTheDocument();
  });

  test('renders a mermaid fenced code block as MermaidDiagram', () => {
    const md = '```mermaid\ngraph TD\n  A --> B\n```';
    render(<MarkdownRenderer>{md}</MarkdownRenderer>);
    const diagram = screen.getByTestId('mermaid-diagram');
    expect(diagram).toBeInTheDocument();
    expect(diagram).toHaveTextContent('graph TD');
  });

  test('renders non-mermaid code blocks as plain code', () => {
    const md = '```js\nconsole.log("hi")\n```';
    render(<MarkdownRenderer>{md}</MarkdownRenderer>);
    expect(screen.getByText(/console\.log/)).toBeInTheDocument();
    expect(screen.queryByTestId('mermaid-diagram')).toBeNull();
  });
});
