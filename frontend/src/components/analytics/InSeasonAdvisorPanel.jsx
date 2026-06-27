import { useCallback, useEffect, useRef, useState } from 'react';
import { buttonPrimary, buttonSecondary } from '@utils/uiStandards';
import { askInSeasonAdvisor } from '@api/analyticsApi';

const QUICK_PROMPTS = [
  'Who should I target on waivers?',
  'Who should I start this week?',
  'Should I sell high on anyone?',
  'Any injury alerts on my roster?',
];

function AdvisorBubble({ text }) {
  return (
    <div
      className="rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900 dark:border-indigo-800/60 dark:bg-indigo-950/40 dark:text-indigo-100"
      data-testid="advisor-bubble"
    >
      {text}
    </div>
  );
}

function UserBubble({ text }) {
  return (
    <div className="flex justify-end" data-testid="user-bubble">
      <div className="max-w-[80%] rounded-lg bg-cyan-600 px-3 py-2 text-sm text-white dark:bg-cyan-700">
        {text}
      </div>
    </div>
  );
}

/**
 * InSeasonAdvisorPanel — conversational in-season advisor.
 *
 * Props:
 *   leagueId         {number}   Current league ID
 *   ownerId          {number}   Current owner ID
 *   season           {number}   Current season year
 *   username         {string}   Display name for context
 *   inSeasonContext  {object}   Full inSeasonInsights bundle (passed as context to advisor)
 */
export default function InSeasonAdvisorPanel({
  leagueId,
  ownerId,
  season,
  username,
  inSeasonContext = null,
}) {
  const [messages, setMessages] = useState([
    {
      type: 'advisor',
      text: 'Ask me anything about your lineup, waivers, or trade opportunities this week.',
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const feedRef = useRef(null);

  const disabled = !leagueId || !ownerId;

  // Auto-scroll on new messages
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages]);

  const sendQuery = useCallback(
    async (query) => {
      if (!query.trim() || loading || disabled) return;
      setError('');
      setMessages((prev) => [...prev, { type: 'user', text: query }]);
      setLoading(true);
      try {
        const res = await askInSeasonAdvisor({
          userQuery: query,
          username,
          leagueId,
          ownerId,
          season,
          inSeasonContext,
        });
        const responseText = (res.data ?? res)?.response ?? 'No response from advisor.';
        setMessages((prev) => [...prev, { type: 'advisor', text: responseText }]);
      } catch {
        setError('Advisor is unavailable. Try again in a moment.');
      } finally {
        setLoading(false);
      }
    },
    [loading, disabled, username, leagueId, ownerId, season, inSeasonContext]
  );

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault();
      const trimmed = inputText.trim();
      if (!trimmed) return;
      sendQuery(trimmed);
      setInputText('');
    },
    [inputText, sendQuery]
  );

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) handleSubmit(e);
    },
    [handleSubmit]
  );

  return (
    <div
      className="flex flex-col rounded-xl border border-indigo-300/60 bg-white sm:rounded-xl dark:border-indigo-800/60 dark:bg-slate-950/80"
      data-testid="in-season-advisor-panel"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-indigo-200 px-4 py-2.5 dark:border-indigo-800/60">
        <span className="text-[11px] font-black uppercase tracking-widest text-indigo-700 dark:text-indigo-300">
          ⚡ In-Season Advisor
        </span>
        {loading && (
          <span className="animate-pulse text-[10px] text-slate-400">Thinking…</span>
        )}
      </div>

      {/* Quick prompts */}
      <div className="flex flex-wrap gap-1.5 border-b border-slate-100 px-3 py-2 dark:border-slate-800">
        {QUICK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => sendQuery(prompt)}
            disabled={loading || disabled}
            className={`${buttonSecondary} rounded-full py-0.5 text-[11px] disabled:opacity-40`}
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* Message feed */}
      <div
        ref={feedRef}
        className="flex-1 space-y-2.5 overflow-y-auto p-3"
        style={{ minHeight: '160px', maxHeight: '340px' }}
        aria-label="In-season advisor chat feed"
        aria-live="polite"
      >
        {messages.map((msg, idx) =>
          msg.type === 'user' ? (
            <UserBubble key={idx} text={msg.text} />
          ) : (
            <AdvisorBubble key={idx} text={msg.text} />
          )
        )}
        {loading && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="inline-flex gap-1">
              <span className="animate-bounce">●</span>
              <span className="animate-bounce" style={{ animationDelay: '0.1s' }}>●</span>
              <span className="animate-bounce" style={{ animationDelay: '0.2s' }}>●</span>
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
          placeholder={disabled ? 'No league context available' : 'Ask about waivers, lineup, or trades…'}
          disabled={disabled || loading}
          aria-label="Advisor query input"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 placeholder-slate-400 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-950 dark:text-slate-200 dark:placeholder-slate-600"
        />
        <button
          type="submit"
          className={`${buttonPrimary} shrink-0`}
          disabled={disabled || loading || !inputText.trim()}
          aria-label="Send query"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
