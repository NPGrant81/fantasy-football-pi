import React, { useState } from 'react';
import axios from 'axios';
import GeminiBadge from './GeminiBadge';

const ChatInterface = () => {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    { role: 'system', text: 'I am your AI GM Advisor. Ask me anything about players, trades, or strategy.' }
  ]);
  const [isLoading, setIsLoading] = useState(false);

  const handleSendMessage = async () => {
    if (!input.trim()) return;

    const userQuery = input;
    // 1. Optimistic UI Update
    setMessages(prev => [...prev, { role: 'user', text: userQuery }]);
    setInput("");
    setIsLoading(true);

    try {
      // 2. Send to backend
      const res = await axios.post(`http://localhost:8000/advisor/ask?user_query=${encodeURIComponent(userQuery)}`);
      
      // 3. Add AI Response
      setMessages(prev => [...prev, { role: 'ai', text: res.data.response }]);
    } catch (err) {
      console.error("Chat error", err);
      setMessages(prev => [...prev, { role: 'system', text: "⚠️ Connection lost. I'm taking a beach break." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 flex flex-col h-[400px]">
      <div className="flex justify-between items-center mb-4 border-b border-slate-800 pb-2">
        <h3 className="font-bold text-slate-200">War Room Advisor</h3>
        <div className="text-xs text-green-400 animate-pulse">● Online</div>
      </div>

      {/* Message History */}
      <div className="flex-1 overflow-y-auto mb-4 space-y-3 p-2">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-3 text-sm ${
              msg.role === 'user' 
                ? 'bg-blue-600 text-white rounded-br-none' 
                : 'bg-slate-800 text-slate-300 rounded-bl-none border border-slate-700'
            }`}>
              {msg.text}
            </div>
          </div>
        ))}
        {isLoading && <div className="text-xs text-slate-500 italic ml-2">Thinking...</div>}
      </div>

      {/* Input Area */}
      <div className="mt-auto">
        <div className="flex gap-2">
            <input 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Ask about a player..." 
            className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white focus:ring-2 focus:ring-blue-500 outline-none"
            />
            <button 
            onClick={handleSendMessage}
            disabled={isLoading}
            className="bg-blue-600 hover:bg-blue-500 text-white font-bold px-4 py-2 rounded-lg transition disabled:opacity-50"
            >
            Send
            </button>
        </div>
        <div className="flex justify-end mt-2">
            <GeminiBadge />
        </div>
      </div>
    </div>
  );
};

export default ChatInterface;
