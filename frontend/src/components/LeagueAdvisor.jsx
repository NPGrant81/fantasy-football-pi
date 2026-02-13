import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'

export default function LeagueAdvisor({ token }) {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  
  // Auto-scroll to bottom of chat
  const messagesEndRef = useRef(null)
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [response, loading])

  const askGemini = () => {
    if (!query) return
    setLoading(true)
    setResponse(null)

    axios.post('http://127.0.0.1:8000/advisor/ask', 
      { user_query: query },
      { 
        params: { user_query: query },
        headers: { Authorization: `Bearer ${token}` } 
      }
    )
    .then(res => {
      setResponse(res.data.response)
      setLoading(false)
    })
    .catch(err => {
      console.error(err)
      setResponse("I'm having trouble reaching the league office right now.")
      setLoading(false)
    })
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      
      {/* CHAT WINDOW */}
      {isOpen && (
        <div className="mb-4 w-[450px] flex flex-col bg-slate-800 border border-slate-600 rounded-lg shadow-2xl overflow-hidden animate-fade-in-up">
          
          {/* HEADER */}
          <div className="bg-slate-700 p-3 border-b border-slate-600 flex justify-between items-center">
            <h3 className="font-bold text-white flex items-center gap-2">
              🤖 League Advisor <span className="text-xs bg-yellow-600 px-2 py-0.5 rounded text-white">AI</span>
            </h3>
            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-white">✕</button>
          </div>
          
          {/* MESSAGES AREA */}
          <div className="flex-grow p-4 bg-slate-900 h-[400px] overflow-y-auto custom-scrollbar">
             
             {/* WELCOME */}
             {!response && !loading && (
               <div className="text-slate-400 text-sm text-center mt-20 italic">
                 "Ask me about sleepers, trade values, or who to start this week..."
               </div>
             )}

             {/* USER QUERY (Optional echo) */}
             {/* If you want to see what you asked, we could add it here, but keeping it clean for now */}

             {/* LOADING */}
             {loading && (
               <div className="flex items-center gap-2 text-yellow-500 text-sm animate-pulse">
                 <span>Thinking...</span>
               </div>
             )}

             {/* AI RESPONSE (RENDERED MARKDOWN) */}
             {response && (
               <div className="bg-slate-800 p-4 rounded text-sm text-slate-200 border border-slate-700 leading-relaxed text-left shadow-inner">
                 <ReactMarkdown 
                   components={{
                     // Style bold text to be Yellow
                     strong: ({node, ...props}) => <span className="font-bold text-yellow-400" {...props} />,
                     // Style headings
                     h3: ({node, ...props}) => <h3 className="text-lg font-bold text-white mt-4 mb-2" {...props} />,
                     // Style lists
                     ul: ({node, ...props}) => <ul className="list-disc pl-5 space-y-1 my-2" {...props} />,
                     li: ({node, ...props}) => <li className="pl-1" {...props} />
                   }}
                 >
                   {response}
                 </ReactMarkdown>
               </div>
             )}
             
             {/* Invisible element to force scroll to bottom */}
             <div ref={messagesEndRef} />
          </div>

          {/* INPUT AREA */}
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

      {/* FLOATING BUTTON */}
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="h-14 w-14 rounded-full bg-gradient-to-r from-yellow-500 to-orange-500 shadow-lg border-2 border-white flex items-center justify-center text-3xl hover:scale-110 transition-transform"
      >
        🤖
      </button>
    </div>
  )
}