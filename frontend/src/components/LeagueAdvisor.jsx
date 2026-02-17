import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'

export default function LeagueAdvisor({ token }) {
  // --- 1.0 STATE & HOOKS ---
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [messages, setMessages] = useState([
    { role: 'ai', text: "Ask me about sleepers, trade values, or who to start this week..." }
  ])

  const messagesEndRef = useRef(null)

  // 1.1 EFFECTS: Auto-scroll to bottom of chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])


  // --- 2.0 LOGIC & HANDLERS ---
  
  // 2.1 ENGINE: The askGemini handler
  const askGemini = async () => {
    if (!query.trim() || loading) return

    // 2.1.1 LOCAL UPDATE: Push user message to UI immediately
    const userMessage = { role: 'user', text: query }
    setMessages(prev => [...prev, userMessage])
    setQuery('')
    setLoading(true)

    try {
      // 2.1.2 EXECUTION: Clean POST with JSON body (Matching Pydantic standard)
      const res = await axios.post('http://127.0.0.1:8000/advisor/ask', 
        { user_query: userMessage.text }, 
        { headers: { Authorization: `Bearer ${token}` } }
      )
      
      // 2.1.3 SUCCESS: Append AI response to thread
      setMessages(prev => [...prev, { role: 'ai', text: res.data.response }])
    } catch (err) {
      console.error("Neural link failed:", err)
      setMessages(prev => [...prev, { 
        role: 'ai', 
        text: "⚠️ I'm having trouble reaching the league office. Check your neural link (API connection)." 
      }])
    } finally {
      setLoading(false)
    }
  }


  // --- 3.0 RENDER ---
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      
      {/* 3.1 CHAT WINDOW */}
      {isOpen && (
        <div className="mb-4 w-[450px] flex flex-col bg-slate-800 border border-slate-600 rounded-lg shadow-2xl overflow-hidden animate-fade-in-up">
          
          {/* HEADER */}
          <div className="bg-slate-700 p-3 border-b border-slate-600 flex justify-between items-center">
            <h3 className="font-bold text-white flex items-center gap-2">
              🤖 League Advisor <span className="text-xs bg-yellow-600 px-2 py-0.5 rounded text-white">AI</span>
            </h3>
            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white">✕</button>
          </div>
          
          {/* 3.2 MESSAGES AREA */}
          <div className="flex-grow p-4 bg-slate-900 h-[400px] overflow-y-auto custom-scrollbar flex flex-col gap-4">
             {messages.map((msg, idx) => (
               <div 
                 key={idx} 
                 className={`max-w-[85%] p-3 rounded text-sm leading-relaxed ${
                   msg.role === 'user' 
                    ? "bg-blue-600 text-white self-end rounded-br-none" 
                    : "bg-slate-800 text-slate-200 border border-slate-700 self-start rounded-bl-none shadow-inner"
                 }`}
               >
                 <ReactMarkdown 
                    components={{
                      strong: ({node, ...props}) => <span className="font-bold text-yellow-400" {...props} />,
                      h3: ({node, ...props}) => <h3 className="text-lg font-bold text-white mt-2 mb-1" {...props} />,
                      ul: ({node, ...props}) => <ul className="list-disc pl-5 space-y-1 my-2" {...props} />,
                      li: ({node, ...props}) => <li className="pl-1" {...props} />
                    }}
                  >
                    {msg.text}
                  </ReactMarkdown>
               </div>
             ))}

             {loading && (
               <div className="flex items-center gap-2 text-yellow-500 text-sm animate-pulse">
                 <span>Thinking...</span>
               </div>
             )}
             
             <div ref={messagesEndRef} />
          </div>

          {/* 3.3 INPUT AREA */}
          <div className="p-3 bg-slate-800 border-t border-slate-600 flex gap-2">
            <input 
              className="flex-grow bg-slate-900 border border-slate-600 rounded px-3 py-3 text-sm text-white focus:border-yellow-500 outline-none"
              placeholder="Ask a question..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && askGemini()}
            />
            <button 
              onClick={askGemini}
              disabled={loading}
              className="bg-yellow-600 hover:bg-yellow-500 text-white px-4 rounded font-bold disabled:opacity-50"
            >
              SEND
            </button>
          </div>
        </div>
      )}

      {/* 3.4 FLOATING BUTTON */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="h-14 w-14 rounded-full bg-gradient-to-r from-yellow-500 to-orange-500 shadow-lg border-2 border-white flex items-center justify-center text-3xl hover:scale-110 transition-transform"
      >
        🤖
      </button>
    </div>
  )
}