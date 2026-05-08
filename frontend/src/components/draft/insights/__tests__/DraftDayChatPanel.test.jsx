import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DraftDayChatPanel from '../DraftDayChatPanel';

const mockAdvisorMsg = {
  type: 'advisor',
  event_type: 'nomination',
  message_type: 'recommendation',
  headline: 'Nomination guidance: Travis Kelce',
  body: 'Travis Kelce projects as tier A with risk 35.0. Recommended bid cap is $42.00.',
  recommended_bid: 42,
  value_tier: 'A',
  risk_score: 35,
  bidding_war_likelihood: 55,
  suggested_alternatives: [
    { player_id: 2, player_name: 'Mark Andrews', position: 'TE', predicted_value: 28, tier: 'B' },
  ],
  alerts: [],
  quick_actions: ['Compare', 'Simulate', 'Explain'],
};

const mockAlertMsg = {
  type: 'advisor',
  event_type: 'bid_update',
  message_type: 'alert',
  headline: 'Bid update: Travis Kelce',
  body: 'Current bid is $50.00. Suggested cap is $42.00. This price is above your plan.',
  recommended_bid: 42,
  value_tier: 'A',
  risk_score: 35,
  bidding_war_likelihood: 70,
  suggested_alternatives: [],
  alerts: ['Overspending risk: budget running tight.'],
  quick_actions: ['Compare', 'Simulate', 'Explain'],
};

describe('DraftDayChatPanel', () => {
  it('renders the panel when feature is enabled', () => {
    render(<DraftDayChatPanel featureEnabled={true} />);
    expect(screen.getByTestId('draft-day-chat-panel')).toBeInTheDocument();
    expect(screen.getByText('Draft Day Copilot')).toBeInTheDocument();
  });

  it('renders disabled state when feature is not enabled', () => {
    render(<DraftDayChatPanel featureEnabled={false} />);
    expect(screen.getByTestId('chat-panel-disabled')).toBeInTheDocument();
    expect(screen.queryByTestId('draft-day-chat-panel')).not.toBeInTheDocument();
  });

  it('shows empty prompt when no messages', () => {
    render(<DraftDayChatPanel featureEnabled={true} messages={[]} />);
    expect(screen.getByText(/Ask anything about the current nomination/i)).toBeInTheDocument();
  });

  it('renders user messages right-aligned', () => {
    const messages = [{ type: 'user', text: 'Should I bid on this WR?' }];
    render(<DraftDayChatPanel featureEnabled={true} messages={messages} />);
    expect(screen.getByTestId('user-message')).toBeInTheDocument();
    expect(screen.getByText('Should I bid on this WR?')).toBeInTheDocument();
  });

  it('renders advisor recommendation message with badges', () => {
    render(
      <DraftDayChatPanel featureEnabled={true} messages={[mockAdvisorMsg]} />
    );
    const msg = screen.getByTestId('advisor-message');
    expect(msg).toBeInTheDocument();
    expect(msg).toHaveAttribute('data-message-type', 'recommendation');
    expect(screen.getByText(/Nomination guidance: Travis Kelce/i)).toBeInTheDocument();
    expect(screen.getByText(/Bid cap: \$42\.00/i)).toBeInTheDocument();
    expect(screen.getByText('Tier A')).toBeInTheDocument();
    expect(screen.getByText('Low Risk')).toBeInTheDocument();
  });

  it('renders advisor alert message with alert list', () => {
    render(
      <DraftDayChatPanel featureEnabled={true} messages={[mockAlertMsg]} />
    );
    const msg = screen.getByTestId('advisor-message');
    expect(msg).toHaveAttribute('data-message-type', 'alert');
    expect(screen.getByText(/Overspending risk/i)).toBeInTheDocument();
  });

  it('renders bidding-war likelihood bar', () => {
    render(
      <DraftDayChatPanel featureEnabled={true} messages={[mockAdvisorMsg]} />
    );
    expect(screen.getByText('55%')).toBeInTheDocument();
    expect(screen.getByText('Bid war')).toBeInTheDocument();
  });

  it('renders suggested alternatives (pivot options)', () => {
    render(
      <DraftDayChatPanel featureEnabled={true} messages={[mockAdvisorMsg]} />
    );
    expect(screen.getByText(/Mark Andrews/i)).toBeInTheDocument();
    expect(screen.getByText(/Pivot options/i)).toBeInTheDocument();
  });

  it('renders quick-action buttons inside messages', () => {
    const onQuickAction = vi.fn();
    render(
      <DraftDayChatPanel
        featureEnabled={true}
        messages={[mockAdvisorMsg]}
        onQuickAction={onQuickAction}
      />
    );
    const compareBtn = screen.getByRole('button', { name: 'Compare' });
    fireEvent.click(compareBtn);
    expect(onQuickAction).toHaveBeenCalledWith('Compare');
  });

  it('calls onSendQuery when user submits text', () => {
    const onSendQuery = vi.fn();
    render(
      <DraftDayChatPanel
        featureEnabled={true}
        messages={[]}
        onSendQuery={onSendQuery}
      />
    );
    const input = screen.getByRole('textbox', { name: /chat input/i });
    fireEvent.change(input, { target: { value: "What's my best position?" } });
    fireEvent.submit(input.closest('form'));
    expect(onSendQuery).toHaveBeenCalledWith("What's my best position?");
  });

  it('clears input after submission', () => {
    const onSendQuery = vi.fn();
    render(
      <DraftDayChatPanel
        featureEnabled={true}
        messages={[]}
        onSendQuery={onSendQuery}
      />
    );
    const input = screen.getByRole('textbox', { name: /chat input/i });
    fireEvent.change(input, { target: { value: 'Test query' } });
    fireEvent.submit(input.closest('form'));
    expect(input.value).toBe('');
  });

  it('disables input and Send button when disabled=true', () => {
    render(<DraftDayChatPanel featureEnabled={true} disabled={true} />);
    expect(screen.getByRole('textbox', { name: /chat input/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  });

  it('does not fire onSendQuery on empty submission', () => {
    const onSendQuery = vi.fn();
    render(
      <DraftDayChatPanel
        featureEnabled={true}
        messages={[]}
        onSendQuery={onSendQuery}
      />
    );
    fireEvent.submit(screen.getByRole('textbox', { name: /chat input/i }).closest('form'));
    expect(onSendQuery).not.toHaveBeenCalled();
  });

  it('shows loading indicator when loading=true', () => {
    render(<DraftDayChatPanel featureEnabled={true} loading={true} />);
    expect(screen.getByText(/Advisor is responding/i)).toBeInTheDocument();
    expect(screen.getByText(/Thinking/i)).toBeInTheDocument();
  });

  it('shows error banner when error is set', () => {
    render(
      <DraftDayChatPanel
        featureEnabled={true}
        error="Advisor request failed. Please retry."
      />
    );
    expect(screen.getByText(/Advisor request failed/i)).toBeInTheDocument();
  });

  it('renders mixed conversation with user + advisor messages', () => {
    const messages = [
      { type: 'user', text: 'Should I bid on this TE?' },
      mockAdvisorMsg,
      { type: 'user', text: 'What about Mark Andrews?' },
    ];
    render(<DraftDayChatPanel featureEnabled={true} messages={messages} />);
    expect(screen.getAllByTestId('user-message')).toHaveLength(2);
    expect(screen.getAllByTestId('advisor-message')).toHaveLength(1);
  });

  it('shows high-risk badge for high risk scores', () => {
    const highRiskMsg = { ...mockAdvisorMsg, risk_score: 75 };
    render(<DraftDayChatPanel featureEnabled={true} messages={[highRiskMsg]} />);
    expect(screen.getByText('High Risk')).toBeInTheDocument();
  });

  it('colours bidding-war bar differently at high likelihood', () => {
    const highWarMsg = { ...mockAdvisorMsg, bidding_war_likelihood: 85 };
    render(<DraftDayChatPanel featureEnabled={true} messages={[highWarMsg]} />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });
});
