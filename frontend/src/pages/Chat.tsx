import React, { useState, useRef, useEffect } from 'react'
import { Head } from '@inertiajs/react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Array<{
    source: string
    title: string
    ref: string
    confidence?: number
  }>
  timestamp: Date
}

export default function Chat({ title }: { title: string }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch('/api/agent/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMessage.content, scenario: 'chat' }),
      })

      const result = await res.json()
      
      // Build a more informative response
      let content = result.summary || result.error || 'No response received'
      
      // Add debug info if available (for troubleshooting)
      if (result.debug && process.env.NODE_ENV === 'development') {
        const debugInfo = `\n\n[Debug: Notion items: ${result.debug.notion_items_count}, Git items: ${result.debug.git_items_count}]`
        content += debugInfo
      }
      
      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: content,
        citations: result.citations || [],
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: `Error: ${error instanceof Error ? error.message : 'Failed to send message'}`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', fontFamily: 'system-ui, sans-serif' }}>
      <Head title={title || 'MCP Agent Chat'} />
      
      <header style={{ padding: '16px 24px', borderBottom: '1px solid #e5e7eb', background: '#fff' }}>
        <h1 style={{ margin: 0, fontSize: '20px', fontWeight: 600 }}>MCP Agent Chat</h1>
        <p style={{ margin: '4px 0 0', fontSize: '14px', color: '#6b7280' }}>
          Ask questions about your Notion docs and Git code
        </p>
      </header>

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px', background: '#f9fafb' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: '#6b7280' }}>
            <p style={{ fontSize: '16px', marginBottom: '8px' }}>Welcome to MCP Agent Chat</p>
            <p style={{ fontSize: '14px', marginBottom: '32px' }}>Ask me anything about your Notion documentation and Git repositories</p>
            
            <div style={{ maxWidth: '600px', margin: '0 auto' }}>
              <p style={{ fontSize: '14px', fontWeight: 500, marginBottom: '16px', color: '#374151' }}>Try asking:</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
                {[
                  'Show all active tasks for API v2 and where they are implemented',
                  'What documentation exists about user authentication?',
                  'Find files related to payment processing',
                  'What tasks in Notion relate to the payment service?',
                  'Does the Git implementation match the Notion documentation?',
                ].map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInput(prompt)
                      setTimeout(() => {
                        const textarea = document.querySelector('textarea') as HTMLTextAreaElement
                        textarea?.focus()
                      }, 100)
                    }}
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      background: '#fff',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      fontSize: '14px',
                      textAlign: 'left',
                      color: '#374151',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = '#f3f4f6'
                      e.currentTarget.style.borderColor = '#3b82f6'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = '#fff'
                      e.currentTarget.style.borderColor = '#e5e7eb'
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
        
        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              marginBottom: '24px',
              display: 'flex',
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
              gap: '12px',
            }}
          >
            <div
              style={{
                maxWidth: '70%',
                padding: '12px 16px',
                borderRadius: '12px',
                background: msg.role === 'user' ? '#3b82f6' : '#fff',
                color: msg.role === 'user' ? '#fff' : '#111827',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              }}
            >
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>{msg.content}</div>
              
              {msg.citations && msg.citations.length > 0 && (
                <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: `1px solid ${msg.role === 'user' ? 'rgba(255,255,255,0.2)' : '#e5e7eb'}` }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, marginBottom: '8px', opacity: 0.8 }}>
                    Sources:
                  </div>
                  {msg.citations.map((cite, idx) => (
                    <div
                      key={idx}
                      style={{
                        fontSize: '12px',
                        marginBottom: '4px',
                        opacity: 0.9,
                      }}
                    >
                      <span style={{ fontWeight: 600 }}>[{cite.source}]</span> {cite.title}
                      {cite.ref && (
                        <span style={{ opacity: 0.7 }}> — {cite.ref}</span>
                      )}
                      {cite.confidence !== undefined && (
                        <span style={{ opacity: 0.6 }}> ({Math.round(cite.confidence * 100)}%)</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {loading && (
          <div style={{ display: 'flex', gap: '12px' }}>
            <div
              style={{
                padding: '12px 16px',
                borderRadius: '12px',
                background: '#fff',
                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
              }}
            >
              <div style={{ display: 'flex', gap: '4px' }}>
                <span style={{ animation: 'pulse 1.5s ease-in-out infinite' }}>●</span>
                <span style={{ animation: 'pulse 1.5s ease-in-out 0.2s infinite' }}>●</span>
                <span style={{ animation: 'pulse 1.5s ease-in-out 0.4s infinite' }}>●</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: '16px 24px', borderTop: '1px solid #e5e7eb', background: '#fff' }}>
        {messages.length > 0 && messages.length < 3 && (
          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
            {[
              'Tell me more',
              'What else?',
              'Show examples',
            ].map((suggestion, idx) => (
              <button
                key={idx}
                onClick={() => {
                  setInput(suggestion)
                  setTimeout(() => {
                    const textarea = document.querySelector('textarea') as HTMLTextAreaElement
                    textarea?.focus()
                  }, 100)
                }}
                style={{
                  padding: '6px 12px',
                  background: '#f3f4f6',
                  border: '1px solid #e5e7eb',
                  borderRadius: '16px',
                  fontSize: '12px',
                  color: '#6b7280',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#e5e7eb'
                  e.currentTarget.style.color = '#374151'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#f3f4f6'
                  e.currentTarget.style.color = '#6b7280'
                }}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
        
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question about your Notion docs or Git code..."
            rows={1}
            style={{
              flex: 1,
              padding: '12px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '14px',
              fontFamily: 'inherit',
              resize: 'none',
              minHeight: '44px',
              maxHeight: '120px',
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement
              target.style.height = 'auto'
              target.style.height = `${Math.min(target.scrollHeight, 120)}px`
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            style={{
              padding: '12px 24px',
              background: '#3b82f6',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: 500,
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              opacity: loading || !input.trim() ? 0.5 : 1,
            }}
          >
            Send
          </button>
        </div>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  )
}

