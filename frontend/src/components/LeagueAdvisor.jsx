import { useState, useRef, useEffect, useCallback } from 'react';
import { bgColors, textColors, borderColors } from '../utils/uiHelpers';
import { GeminiBadge } from './chat';
// ESLint doesn't properly detect JSX component usage, so suppressions below

import { FiSend } from 'react-icons/fi';
import apiClient from '@api/client';

import ReactMarkdown from 'react-markdown';

export default function ChatInterface({ initialQuery = '' }) {
  // --- USER/LEAGUE CONTEXT ---
  const [userInfo, setUserInfo] = useState({ username: '', leagueId: null });
  useEffect(() => {
    async function fetchUserLeague() {
      try {
        const userRes = await apiClient.get('/auth/me');
        setUserInfo({
          username: userRes.data.username,
          leagueId: userRes.data.league_id,
        });
      } catch {
        setUserInfo({ username: '', leagueId: null });
      }
    }
    fetchUserLeague();
  }, []);
  // --- 1.1 STATE MANAGEMENT ---
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      role: 'ai',
      text: 'I am your Gemini GM Advisor. Ask me about sleepers, value picks, or roster strategy.',
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isAvailable, setIsAvailable] = useState(true);
  const [retryQuery, setRetryQuery] = useState('');
  const [isRetryCooldown, setIsRetryCooldown] = useState(false);
  const scrollRef = useRef(null);
  const retryCooldownRef = useRef(null);

  useEffect(() => {
    return () => {
      if (retryCooldownRef.current) {
        clearTimeout(retryCooldownRef.current);
      }
    };
  }, []);

  // --- 2.1 MESSAGE HANDLER (Defined early for use in effects) ---
  const handleSendMessage = useCallback(
    async (queryOverride = null) => {
      const activeQuery = queryOverride || input;
      if (!activeQuery.trim() || isLoading || !isAvailable) return;

      // 2.1.1 LOCAL UPDATE
      setMessages((prev) => [...prev, { role: 'user', text: activeQuery }]);
      if (!queryOverride) setInput('');
      setRetryQuery('');
      setIsLoading(true);

      try {
        // 2.1.2 EXECUTION: JSON body delivery (Standard-compliant)
        const res = await apiClient.post(
          '/advisor/ask',
          {
            user_query: activeQuery,
            username: userInfo.username,
            league_id: userInfo.leagueId,
          },
          {
            timeout: 30000,
          }
        );

        // 2.1.3 SUCCESS
        setMessages((prev) => [
          ...prev,
          { role: 'ai', text: res.data.response },
        ]);
        setRetryQuery('');
      } catch (error) {
        console.error('Neural Link Error:', error);
        const isTimeout =
          error?.code === 'ECONNABORTED' ||
          (typeof error?.message === 'string' &&
            error.message.toLowerCase().includes('timeout'));
        setRetryQuery(isTimeout ? activeQuery : '');

        setMessages((prev) => [
          ...prev,
          {
            role: 'ai',
            text: isTimeout
              ? '⚠️ The advisor is still thinking and timed out. Please retry in a few seconds, or ask a shorter question.'
              : '⚠️ The neural link to the Pi is down. Check your connection.',
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading, isAvailable, userInfo.leagueId, userInfo.username]
  );

  useEffect(() => {
    apiClient
      .get('/advisor/status')
      .then((res) => setIsAvailable(Boolean(res.data?.enabled)))
      .catch(() => setIsAvailable(false));
  }, []);

  const handleRetry = () => {
    if (!retryQuery || isLoading || isRetryCooldown) return;
    setIsRetryCooldown(true);
    handleSendMessage(retryQuery);
    retryCooldownRef.current = setTimeout(() => {
      setIsRetryCooldown(false);
    }, 1500);
  };

  // --- 1.2 AUTO-SCROLL ENGINE ---
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // --- 1.3 MOUNT ENGINE (Prompt-to-Window Transition) ---
  useEffect(() => {
    if (initialQuery) {
      setIsOpen(true); // Ensure window is open if a query is passed
      handleSendMessage(initialQuery);
    }
  }, [initialQuery, handleSendMessage]);

  // --- 3.1 RENDER: CONTAINER ---
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      {/* 3.2 CHAT WINDOW */}
      {isOpen && (
        <div
          className={`mb-4 w-[450px] flex flex-col ${bgColors.main} border ${borderColors.main} rounded-2xl shadow-2xl overflow-hidden animate-fade-in-up`}
        >
          {/* HEADER */}
          <div
            className={`${bgColors.header} p-4 border-b ${borderColors.main} flex justify-between items-center`}
          >
            <h3
              className={`font-black uppercase tracking-tighter ${textColors.main} italic`}
            >
              War Room Advisor
            </h3>
            <div className="flex items-center gap-3">
              <GeminiBadge />
              <button
                onClick={() => setIsOpen(false)}
                className={`${textColors.secondary} hover:${textColors.main} transition-colors`}
              >
                ✕
              </button>
            </div>
          </div>

          {/* MESSAGE VIEWPORT */}
          <div
            className={`flex-1 overflow-y-auto p-4 space-y-4 max-h-[350px] min-h-[200px] custom-scrollbar ${bgColors.section}`}
          >
            {!isAvailable && (
              <div className="rounded-lg border border-yellow-700 bg-yellow-900/30 p-3 text-xs text-yellow-200">
                Advisor is offline. Set `GEMINI_API_KEY` on the backend to
                enable chat.
              </div>
            )}
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl p-3 text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? `${bgColors.accent} ${textColors.main} rounded-tr-none shadow-lg`
                      : `${bgColors.main} text-slate-200 rounded-tl-none border ${borderColors.main}`
                  }`}
                >
                  <ReactMarkdown
                    components={{
                      strong: ({ ...props }) => (
                        <span
                          className={`font-bold ${textColors.warning}`}
                          {...props}
                        />
                      ),
                      ul: ({ ...props }) => (
                        <ul
                          className="list-disc pl-5 space-y-1 my-2"
                          {...props}
                        />
                      ),
                      li: ({ ...props }) => <li className="pl-1" {...props} />,
                    }}
                  >
                    {msg.text}
                  </ReactMarkdown>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div
                  className={`${bgColors.main} p-3 rounded-2xl rounded-tl-none border ${borderColors.main}`}
                >
                  <span className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce"></span>
                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:0.2s]"></span>
                    <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce [animation-delay:0.4s]"></span>
                  </span>
                </div>
              </div>
            )}
            <div ref={scrollRef} />
          </div>

          {/* INPUT AREA */}
          <div className={`p-4 ${bgColors.main} border-t ${borderColors.main}`}>
            {retryQuery && !isLoading && (
              <div className="mb-2 flex justify-end">
                <button
                  onClick={handleRetry}
                  disabled={isRetryCooldown}
                  className={`text-xs ${textColors.warning} hover:underline disabled:opacity-60 disabled:no-underline`}
                >
                  Retry last question
                </button>
              </div>
            )}
            <div
              className={`flex gap-2 ${bgColors.card} p-1 rounded-xl border ${borderColors.main} focus-within:${borderColors.accent} transition-colors`}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                placeholder="Search players or ask advice..."
                className={`flex-1 bg-transparent px-3 py-2 ${textColors.main} text-sm outline-none`}
              />
              <button
                onClick={() => handleSendMessage()}
                disabled={isLoading || !isAvailable}
                className={`${bgColors.accent} hover:bg-blue-500 ${textColors.main} p-2 rounded-lg transition disabled:opacity-30 active:scale-95`}
              >
                <FiSend />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 3.3 FLOATING TOGGLE BUTTON */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="h-14 w-14 rounded-full bg-gradient-to-r from-yellow-500 to-orange-500 shadow-lg border-2 border-white flex items-center justify-center text-3xl hover:scale-110 transition-transform active:scale-95"
      >
        🤖
      </button>
    </div>
  );
}
