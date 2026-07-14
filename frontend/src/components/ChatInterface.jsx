import React, { useState, useRef, useEffect } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { sendMessageToAgent, addLocalUserMessage, clearEmailDraft } from '../store/crmSlice';
import { Send, Mail, Clipboard, Check } from 'lucide-react';

export default function ChatInterface() {
  const dispatch = useDispatch();
  const { chatHistory, selectedHcpId, agentTyping, emailDraft } = useSelector((state) => state.crm);
  const [input, setInput] = useState('');
  const [copied, setCopied] = useState(false);
  
  const chatEndRef = useRef(null);

  // Auto-scroll to bottom of chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, agentTyping]);

  const handleSend = async (textToSend) => {
    const text = textToSend || input;
    if (!text.trim()) return;

    if (!textToSend) setInput('');
    
    // Clear previous email draft when starting a new message
    dispatch(clearEmailDraft());
    
    // 1. Add user message locally
    dispatch(addLocalUserMessage(text));
    
    // 2. Query LangGraph Backend Agent
    // If selectedHcpId is null, use a default value (e.g. 1) to prevent errors
    const activeHcpId = selectedHcpId || 1;
    dispatch(sendMessageToAgent({
      message: text,
      hcpId: activeHcpId,
      chatHistory: chatHistory
    }));
  };

  const handleCopy = () => {
    if (!emailDraft) return;
    const fullText = `Subject: ${emailDraft.subject}\n\n${emailDraft.body}`;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="chat-interface-wrapper split-right-panel">
      <div className="chat-container glass-card">
        <div className="chat-header">
          <div className="chat-title-row">
            <span className="sparkle-avatar">G</span>
            <div className="header-meta">
              <h3>AI Assistant</h3>
              <span className="subtext-label">Log interaction details here via chat</span>
            </div>
          </div>
        </div>

        <div className="chat-messages">
          {chatHistory.length === 0 && (
            <div className="chat-welcome-box">
              <div className="welcome-info-card">
                <p>
                  Log interaction details here (e.g., "Met Dr. Smith, discussed Prodo-X efficacy, 
                  positive sentiment, shared brochure") or ask for help.
                </p>
              </div>
            </div>
          )}

          {chatHistory.map((msg, idx) => (
            <div key={idx} className={`chat-bubble-container ${msg.role}`}>
              <div className={`chat-bubble ${msg.role}`}>
                <div className="bubble-content">{msg.content}</div>
              </div>
            </div>
          ))}

          {agentTyping && (
            <div className="chat-bubble-container assistant">
              <div className="chat-bubble assistant typing">
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="chat-input-form">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe Interaction..."
            disabled={agentTyping}
            rows={1}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <button 
            type="submit" 
            disabled={agentTyping || !input.trim()} 
            className="btn-send-chat-log"
          >
            <div className="a-badge">A</div>
            <div className="btn-txt">Log</div>
          </button>
        </form>
      </div>

      {emailDraft && (
        <div className="email-draft-panel glass-card slide-in">
          <div className="panel-header">
            <span className="mail-icon">✉️</span>
            <h4>AI Generated Email Draft</h4>
          </div>
          <div className="email-content">
            <div className="email-field">
              <span className="lbl">To:</span>
              <span className="val">{emailDraft.to}</span>
            </div>
            <div className="email-field">
              <span className="lbl">Subject:</span>
              <span className="val">{emailDraft.subject}</span>
            </div>
            <pre className="email-body">{emailDraft.body}</pre>
          </div>
          <button onClick={handleCopy} className="btn-copy-email secondary-btn">
            {copied ? (
              <>
                <Check size={14} className="copied-icon" />
                <span>Copied!</span>
              </>
            ) : (
              <>
                <Clipboard size={14} />
                <span>Copy Draft Email</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
