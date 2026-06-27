import { useCallback, useEffect, useRef, useState } from 'react';
import { buttonPrimary, buttonSecondary } from '@utils/uiStandards';

/* ignore-breakpoints */

/**
 * Message type → border + header colour tokens (light-first).
 */
const MESSAGE_STYLES = {
  recommendation: {
    border: 'border-cyan-300 dark:border-cyan-700',
    header: 'text-cyan-700 dark:text-cyan-300',
    bg: 'bg-cyan-50 dark:bg-cyan-950/30',
  },
  alert: {
    border: 'border-amber-300 dark:border-amber-700',
    header: 'text-amber-700 dark:text-amber-300',
    bg: 'bg-amber-50 dark:bg-amber-950/30',
  },
  explanation: {
    border: 'border-indigo-300 dark:border-indigo-700',
    header: 'text-indigo-700 dark:text-indigo-300',
    bg: 'bg-indigo-50 dark:bg-indigo-950/30',
  },
  comparison: {
    border: 'border-purple-300 dark:border-purple-700',
    header: 'text-purple-700 dark:text-purple-300',
    bg: 'bg-purple-50 dark:bg-purple-950/30',
  },
  strategy_summary: {
    border: 'border-slate-300 dark:border-slate-600',
    header: 'text-slate-700 dark:text-slate-300',
    bg: 'bg-slate-50 dark:bg-slate-900/50',
  },
};

const MESSAGE_TYPE_LABELS = {
  recommendation: 'Recommendation',
  alert: 'Alert',
  explanation: 'Explanation',
  comparison: 'Comparison',
  strategy_summary: 'Strategy Update',
};

const TIER_COLOURS = {
  S: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  A: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300',
  B: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  C: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  D: 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300',
};

function TierBadge({ tier }) {
  if (!tier) return null;
  const colour = TIER_COLOURS[String(tier).toUpperCase()] || TIER_COLOURS.C;
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none ${colour}`}
      title={`Value tier ${tier}`}
    >
      Tier {tier}
    </span>
  );
}

function RiskBadge({ riskScore }) {
  if (riskScore == null) return null;
  const risk = Number(riskScore);
  let label, colour;
  if (risk < 45) {
    label = 'Low Risk';
    colour = 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300';
  } else if (risk < 70) {
    label = 'Mod Risk';
    colour = 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300';
  } else {
    label = 'High Risk';
    colour = 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300';
  }
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase leading-none ${colour}`}
      title={`Risk score: ${risk.toFixed(0)}`}
    >
      {label}
    </span>
  );
}

function BiddingWarBar({ likelihood }) {
  if (likelihood == null) return null;
  const pct = Math.min(100, Math.max(0, Number(likelihood)));
  const barColour = pct >= 70 ? 'bg-rose-500' : pct >= 45 ? 'bg-amber-500' : 'bg-emerald-500';
  return (
    <div
      className="flex items-center gap-1.5"
      title={`Bidding-war likelihood: ${pct.toFixed(0)}%`}
    >
      <span className="text-[10px] text-slate-500 dark:text-slate-400 whitespace-nowrap">
        Bid war
      </span>
      <div className="h-1.5 w-16 overflow-hidden rounded bg-slate-200 dark:bg-slate-700">
        <div className={`h-1.5 ${barColour}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] font-semibold text-slate-600 dark:text-slate-300">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

function AdvisorMessage({ msg, onQuickAction }) {
  const style = MESSAGE_STYLES[msg.message_type] || MESSAGE_STYLES.strategy_summary;
  const typeLabel = MESSAGE_TYPE_LABELS[msg.message_type] || msg.message_type;
  const hasAlerts = Array.isArray(msg.alerts) && msg.alerts.length > 0;
  const hasAlternatives = Array.isArray(msg.suggested_alternatives) && msg.suggested_alternatives.length > 0;
  const hasBadges = msg.value_tier != null || msg.risk_score != null || msg.bidding_war_likelihood != null;

  return (
    <div
      className={`rounded-lg border ${style.border} ${style.bg} p-3 text-sm`}
      data-testid="advisor-message"
      data-message-type={msg.message_type}
    >
      {/* Header row */}
      <div className="mb-1.5 flex flex-wrap items-center gap-2">
        <span className={`text-[10px] font-black uppercase tracking-widest ${style.header}`}>
          {typeLabel}
        </span>
        {msg.recommended_bid != null && (
          <span className="text-[10px] font-bold text-emerald-700 dark:text-emerald-300">
            Bid cap: ${Number(msg.recommended_bid).toFixed(2)}
          </span>
        )}
        {hasBadges && (
          <>
            <TierBadge tier={msg.value_tier} />
            <RiskBadge riskScore={msg.risk_score} />
            <BiddingWarBar likelihood={msg.bidding_war_likelihood} />
          </>
        )}
      </div>

      {/* Headline */}
      <p className="mb-1 font-semibold text-slate-800 dark:text-slate-100">{msg.headline}</p>

      {/* Body */}
      <p className="text-slate-700 dark:text-slate-300">{msg.body}</p>

      {/* Alerts */}
      {hasAlerts && (
        <ul className="mt-2 space-y-0.5 border-t border-amber-200 pt-2 dark:border-amber-900/60">
          {msg.alerts.map((alert, i) => (
            <li
              key={`alert-${i}`}
              className="text-[11px] text-amber-700 dark:text-amber-300"
            >
              ⚠ {alert}
            </li>
          ))}
        </ul>
      )}

      {/* Alternatives */}
      {hasAlternatives && (
        <div className="mt-2 border-t border-slate-200 pt-2 dark:border-slate-700">
          <p className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-500">
            Pivot options
          </p>
          <div className="flex flex-wrap gap-1.5">
            {msg.suggested_alternatives.map((alt) => (
              <span
                key={alt.player_id}
                className="rounded bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                title={`Tier ${alt.tier || '?'} · $${Number(alt.predicted_value || 0).toFixed(0)} projected`}
              >
                {alt.player_name}
                {alt.position ? ` (${alt.position})` : ''}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Quick-action buttons */}
      {Array.isArray(msg.quick_actions) && msg.quick_actions.length > 0 && onQuickAction && (
        <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-slate-200 pt-2.5 dark:border-slate-700">
          {msg.quick_actions.map((action) => (
            <button
              key={action}
              type="button"
              className={`${buttonSecondary} py-0.5 text-[11px]`}
              onClick={() => onQuickAction(action)}
            >
              {action}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function UserMessage({ text }) {
  return (
    <div className="flex justify-end" data-testid="user-message">
      <div className="max-w-[80%] rounded-lg bg-cyan-600 px-3 py-2 text-sm text-white dark:bg-cyan-700">
        {text}
      </div>
    </div>
  );
}

/**
 * DraftDayChatPanel — conversational interface for Draft Day Mode.
 *
 * Props:
 *   messages          {Array}    Conversation history. Each item has {type:'user'|'advisor', text?, ...DraftDayMessageResponse}
 *   onSendQuery       {Function} Called with (queryText, quickAction?) when user submits
 *   onNomination      {Function} Called when user wants to trigger a nomination event
 *   loading           {boolean}
 *   error             {string}
 *   disabled          {boolean}  True when no player/league context is available
 *   featureEnabled    {boolean}  Feature-flag gate; renders disabled state when false
 */
export default function DraftDayChatPanel({
  messages = [],
  onSendQuery,
  onQuickAction,
  loading = false,
  error = '',
  disabled = false,
  featureEnabled = true,
}) {
  const [inputText, setInputText] = useState('');
  const feedRef = useRef(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault();
      const trimmed = inputText.trim();
      if (!trimmed || loading || disabled) return;
      onSendQuery?.(trimmed);
      setInputText('');
    },
    [inputText, loading, disabled, onSendQuery]
  );

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        handleSubmit(e);
      }
    },
    [handleSubmit]
  );

  if (!featureEnabled) {
    return (
      <div
        className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-400"
        data-testid="chat-panel-disabled"
      >
        Draft Day Mode is not enabled in this environment.
      </div>
    );
  }

  return (
    <div
      className="flex h-full flex-col rounded-lg border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-950/80"
      data-testid="draft-day-chat-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-700">
        <span className="text-[11px] font-black uppercase tracking-widest text-indigo-700 dark:text-indigo-300">
          Draft Day Copilot
        </span>
        {loading && (
          <span className="animate-pulse text-[10px] text-slate-400">
            Thinking…
          </span>
        )}
      </div>

      {/* Message feed */}
      <div
        ref={feedRef}
        className="flex-1 space-y-2.5 overflow-y-auto p-3"
        style={{ minHeight: '220px', maxHeight: '480px' }}
        aria-label="Draft Day chat feed"
        aria-live="polite"
      >
        {messages.length === 0 && !loading && (
          <p className="py-6 text-center text-xs text-slate-400 dark:text-slate-500">
            Ask anything about the current nomination, or type a player name to get guidance.
          </p>
        )}

        {messages.map((msg, idx) =>
          msg.type === 'user' ? (
            <UserMessage key={idx} text={msg.text} />
          ) : (
            <AdvisorMessage key={idx} msg={msg} onQuickAction={onQuickAction} />
          )
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-slate-400" aria-label="Advisor is responding">
            <span className="inline-flex gap-1">
              <span className="animate-bounce delay-0">●</span>
              <span className="animate-bounce delay-100">●</span>
              <span className="animate-bounce delay-200">●</span>
            </span>
            Advisor is responding…
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="border-t border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300">
          {error}
        </div>
      )}

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex gap-2 border-t border-slate-200 p-2 dark:border-slate-700"
      >
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={disabled ? 'Select a player and owner to enable chat' : 'Ask: Should I bid on this WR?'}
          disabled={disabled || loading}
          aria-label="Chat input"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 placeholder-slate-400 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:placeholder-slate-600"
        />
        <button
          type="submit"
          className={`${buttonPrimary} shrink-0`}
          disabled={disabled || loading || !inputText.trim()}
          aria-label="Send"
        >
          Send
        </button>
      </form>
    </div>
  );
}
