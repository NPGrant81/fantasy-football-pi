import { render, screen, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// Mock mermaid so tests don't depend on a real browser SVG renderer
vi.mock('mermaid', () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn().mockResolvedValue({ svg: '<svg data-testid="mermaid-svg"></svg>' }),
  },
}));

import mermaid from 'mermaid';
import MermaidDiagram from '../src/components/MermaidDiagram';

describe('MermaidDiagram', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mermaid.render.mockResolvedValue({ svg: '<svg data-testid="mermaid-svg"></svg>' });
  });

  test('shows loading state initially then renders SVG', async () => {
    render(<MermaidDiagram chart={'graph TD\n  A --> B'} />);
    // Initially shows loading text
    expect(screen.getByText(/rendering diagram/i)).toBeInTheDocument();
    // After render resolves, SVG appears
    await waitFor(() =>
      expect(document.querySelector('[data-testid="mermaid-svg"]')).toBeTruthy()
    );
  });

  test('shows error message when mermaid.render() rejects', async () => {
    mermaid.render.mockRejectedValueOnce(new Error('Parse error in diagram'));

    render(<MermaidDiagram chart="invalid chart syntax !!!" />);
    await waitFor(() =>
      expect(screen.getByRole('alert')).toBeInTheDocument()
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Diagram error:');
    expect(screen.getByRole('alert')).toHaveTextContent('Parse error in diagram');
  });

  test('calls mermaid.render with the provided chart content', async () => {
    const chart = 'graph TD\n  A --> B';
    render(<MermaidDiagram chart={chart} />);
    await waitFor(() => expect(mermaid.render).toHaveBeenCalled());
    const callArgs = mermaid.render.mock.calls[0];
    expect(callArgs[1]).toBe(chart);
  });
});
