import { render, screen, fireEvent } from '@testing-library/react';
import ManageScoringRules from '../src/pages/commissioner/ManageScoringRules';

// basic smoke test to ensure new fields exist and can add rule

describe('ManageScoringRules page', () => {
  test('renders form fields for extended rule options', () => {
    render(<ManageScoringRules />);
    expect(screen.getByPlaceholderText(/Category/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Event Name/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Min/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Max/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Point Value/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Positions/i)).toBeInTheDocument();
    expect(screen.getByText(/Flat Bonus/i)).toBeInTheDocument();
  });

  test('can add a new rule to list', () => {
    render(<ManageScoringRules />);
    fireEvent.change(screen.getByPlaceholderText(/Category/i), {
      target: { value: 'passing' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Event Name/i), {
      target: { value: 'Test' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Point Value/i), {
      target: { value: '1' },
    });
    fireEvent.change(screen.getByPlaceholderText(/Positions/i), {
      target: { value: 'QB' },
    });
    fireEvent.click(screen.getByText(/Add Rule/i));
    expect(screen.getByText('Test')).toBeInTheDocument();
  });
});
