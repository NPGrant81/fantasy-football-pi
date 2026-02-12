import React, { useState } from 'react';

const LeagueAdvisor = () => {
  const [isOpen, setIsOpen] = useState(false); // Controls if chat is visible
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);

  // Toggle the chat window
  const toggleChat = () => setIsOpen(!isOpen);

  const askGemini = async (e) => {
    e.preventDefault();
    if (!query) return;

    setLoading(true);
    // Don't clear response immediately so user can see previous answer while waiting
    
    try {
      const url = new URL('http://localhost:8000/advisor/ask');
      url.searchParams.append('user_query', query);
      
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!res.ok) throw new Error('Failed to get advice');
      const data = await res.json();
      setResponse(data.response);
    } catch (err) {
      setResponse("Error: The Commissioner is out to lunch. Try again later.");
    } finally {
      setLoading(false);
      setQuery(''); // Clear input after asking
    }
  };

  return (
    <>
      {/* 1. THE CHAT WINDOW (Only shows when isOpen is true) */}
      {isOpen && (
        <div style={styles.chatWindow}>
          <div style={styles.header}>
            <span style={{ fontWeight: 'bold' }}>🤖 League Advisor</span>
            <button onClick={toggleChat} style={styles.closeBtn}>×</button>
          </div>

          <div style={styles.body}>
            {response ? (
              <div style={styles.messageBot}>
                <strong>Commissioner AI:</strong>
                <p style={{ whiteSpace: 'pre-wrap', marginTop: '5px' }}>{response}</p>
              </div>
            ) : (
              <p style={{ color: '#888', textAlign: 'center', marginTop: '50px' }}>
                Ask me about trades, waivers, or who to start!
              </p>
            )}
          </div>

          <form onSubmit={askGemini} style={styles.footer}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask a question..."
              style={styles.input}
              disabled={loading}
            />
            <button type="submit" disabled={loading} style={styles.sendBtn}>
              {loading ? '...' : 'Send'}
            </button>
          </form>
        </div>
      )}

      {/* 2. THE FLOATING BUTTON (Always visible) */}
      <button onClick={toggleChat} style={styles.floatingBtn}>
        {isOpen ? 'Close' : '🤖 Advice'}
      </button>
    </>
  );
};

// CSS-in-JS Styles for the "Floating" effect
const styles = {
  floatingBtn: {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    backgroundColor: '#007bff',
    color: 'white',
    border: 'none',
    borderRadius: '50px',
    padding: '15px 25px',
    fontSize: '16px',
    cursor: 'pointer',
    boxShadow: '0 4px 10px rgba(0,0,0,0.2)',
    zIndex: 1000, // Ensure it sits on top of everything
    fontWeight: 'bold',
  },
  chatWindow: {
    position: 'fixed',
    bottom: '80px', // Sits just above the button
    right: '20px',
    width: '350px',
    height: '500px',
    backgroundColor: 'white',
    borderRadius: '10px',
    boxShadow: '0 5px 20px rgba(0,0,0,0.3)',
    zIndex: 1000,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    border: '1px solid #ddd',
  },
  header: {
    backgroundColor: '#007bff',
    color: 'white',
    padding: '15px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'white',
    fontSize: '20px',
    cursor: 'pointer',
  },
  body: {
    flex: 1,
    padding: '15px',
    overflowY: 'auto',
    backgroundColor: '#f9f9f9',
  },
  messageBot: {
    backgroundColor: '#e9ecef',
    padding: '10px',
    borderRadius: '10px',
    fontSize: '14px',
    lineHeight: '1.4',
  },
  footer: {
    padding: '10px',
    borderTop: '1px solid #eee',
    display: 'flex',
    backgroundColor: 'white',
  },
  input: {
    flex: 1,
    padding: '10px',
    borderRadius: '5px',
    border: '1px solid #ddd',
    marginRight: '10px',
  },
  sendBtn: {
    padding: '10px 15px',
    backgroundColor: '#28a745',
    color: 'white',
    border: 'none',
    borderRadius: '5px',
    cursor: 'pointer',
  }
};

export default LeagueAdvisor;
