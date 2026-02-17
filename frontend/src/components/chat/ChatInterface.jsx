import { useState, useRef, useEffect } from 'react';
import { FiSend } from 'react-icons/fi';
import apiClient from '@api/client';
import GeminiBadge from './GeminiBadge';
import ReactMarkdown from 'react-markdown';

export default function ChatInterface({ initialQuery = '' }) {
  // --- 1.1 STATE MANAGEMENT ---
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      role: 'ai',
      text: 'I am your Gemini GM Advisor. Ask me about sleepers, value picks, or roster strategy.',
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef(null);

  // --- 1.2 AUTO-SCROLL ENGINE ---
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // --- 1.3 MOUNT ENGINE (Prompt-to-Window Transition) ---
  useEffect(() => {
    if (initialQuery) {
      handleSendMessage(initialQuery);
    }
  }, []);

  // --- 2.1 MESSAGE HANDLER ---
  const handleSendMessage = async (queryOverride = null) => {
    const activeQuery = queryOverride || input;
    if (!activeQuery.trim() || isLoading) return;

    // 2.1.1 LOCAL UPDATE
    setMessages((prev) => [...prev, { role: 'user', text: activeQuery }]);
    if (!queryOverride) setInput('');
    setIsLoading(true);

    try {
      // 2.1.2 EXECUTION: POST with JSON body (Fixes the 422 error)
      const res = await apiClient.post('/advisor/ask', {
        user_query: activeQuery,
      });

      // 2.1.3 SUCCESS
      setMessages((prev) => [...prev, { role: 'ai', text: res.data.response }]);
    } catch (err) {
      console.error('Neural Link Error:', err);
      setMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          text: '⚠️ The neural link to the Pi is down. Check your connection.',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // --- 3.1 RENDER: CONTAINER ---
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl flex flex-col h-[500px] shadow-2xl overflow-hidden">
      {/* 3.2 HEADER */}
      <div className="bg-slate-950/50 p-4 border-b border-slate-800 flex justify-between items-center">
        <h3 className="font-black uppercase tracking-tighter text-white italic">
          War Room Advisor
        </h3>
        <GeminiBadge />
      </div>

      {/* 3.3 MESSAGE VIEWPORT */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar bg-slate-950/20">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl p-3 text-sm leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none shadow-lg shadow-blue-900/20'
                  : 'bg-slate-800 text-slate-200 rounded-tl-none border border-slate-700'
              }`}
            >
              <ReactMarkdown
                components={{
                  strong: ({ node, ...props }) => (
                    <span className="font-bold text-yellow-400" {...props} />
                  ),
                  ul: ({ node, ...props }) => (
                    <ul className="list-disc pl-5 space-y-1 my-2" {...props} />
                  ),
                  li: ({ node, ...props }) => (
                    <li className="pl-1" {...props} />
                  ),
                }}
              >
                {msg.text}
              </ReactMarkdown>
            </div>
          </div>
        ))}

        {/* 3.4 LOADING INDICATOR */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-slate-800 p-3 rounded-2xl rounded-tl-none border border-slate-700">
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

      {/* 3.5 INPUT AREA */}
      <div className="p-4 bg-slate-900 border-t border-slate-800">
        <div className="flex gap-2 bg-slate-950 p-1 rounded-xl border border-slate-700 focus-within:border-blue-500 transition-colors">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Search players or ask advice..."
            className="flex-1 bg-transparent px-3 py-2 text-white text-sm outline-none"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={isLoading}
            className="bg-blue-600 hover:bg-blue-500 text-white p-2 rounded-lg transition disabled:opacity-30 active:scale-95"
          >
            <FiSend />
          </button>
        </div>
      </div>
    </div>
  );
}
