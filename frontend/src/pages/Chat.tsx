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
      
      let content = result.summary || result.error || 'No response received'
      
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
        content: `I'm sorry, but I encountered an error: ${error instanceof Error ? error.message : 'Failed to send message'}. Please try again.`,
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

  const getSourceIcon = (source: string) => {
    if (source === 'notion') return '📄'
    if (source === 'git') return '💻'
    return '📎'
  }

  const getSourceColor = (source: string, isUser: boolean) => {
    if (isUser) {
      return {
        bg: 'rgba(255, 255, 255, 0.15)',
        text: 'rgba(255, 255, 255, 0.95)',
        border: 'rgba(255, 255, 255, 0.25)',
        hover: 'rgba(255, 255, 255, 0.25)',
      }
    }
    if (source === 'notion') {
      return {
        bg: '#f3e8ff',
        text: '#7c3aed',
        border: '#e9d5ff',
        hover: '#e9d5ff',
      }
    }
    if (source === 'git') {
      return {
        bg: '#dbeafe',
        text: '#1e40af',
        border: '#bfdbfe',
        hover: '#bfdbfe',
      }
    }
    return {
      bg: '#f3f4f6',
      text: '#374151',
      border: '#e5e7eb',
      hover: '#e5e7eb',
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
      background: 'linear-gradient(135deg, #f8fafc 0%, #e0e7ff 50%, #ddd6fe 100%)',
      WebkitFontSmoothing: 'antialiased',
      MozOsxFontSmoothing: 'grayscale',
    }}>
      <Head title={title || 'MCP Agent Chat'} />
      
      <header style={{
        background: 'rgba(255, 255, 255, 0.85)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderBottom: '1px solid rgba(226, 232, 240, 0.5)',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}>
        <div style={{ maxWidth: '896px', margin: '0 auto', padding: '20px 24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '48px',
              height: '48px',
              borderRadius: '12px',
              background: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(59, 130, 246, 0.3)',
            }}>
              <span style={{ color: 'white', fontSize: '20px', fontWeight: 'bold' }}>M</span>
            </div>
            <div>
              <h1 style={{
                margin: 0,
                fontSize: '20px',
                fontWeight: 700,
                background: 'linear-gradient(135deg, #1e293b 0%, #475569 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                backgroundClip: 'text',
              }}>
                MCP Agent
              </h1>
              <p style={{ margin: '2px 0 0', fontSize: '13px', color: '#64748b' }}>
                Your intelligent assistant for Notion & GitHub
              </p>
            </div>
          </div>
        </div>
      </header>

      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '24px 16px',
      }}>
        <div style={{ maxWidth: '896px', margin: '0 auto' }}>
          {messages.length === 0 && (
            <div style={{ textAlign: 'center', padding: '48px 16px' }}>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '80px',
                height: '80px',
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
                marginBottom: '24px',
                boxShadow: '0 8px 24px rgba(59, 130, 246, 0.3)',
                animation: 'pulse-slow 3s ease-in-out infinite',
              }}>
                <span style={{ fontSize: '40px' }}>✨</span>
              </div>
              <h2 style={{
                fontSize: '28px',
                fontWeight: 700,
                color: '#1e293b',
                marginBottom: '8px',
              }}>
                Welcome to MCP Agent
              </h2>
              <p style={{
                color: '#475569',
                marginBottom: '32px',
                maxWidth: '512px',
                margin: '0 auto 32px',
                lineHeight: '1.6',
              }}>
                I'm here to help you connect your Notion documentation with your GitHub code. 
                Ask me anything, and I'll find the relevant information for you.
              </p>
              
              <div style={{ maxWidth: '768px', margin: '0 auto' }}>
                <p style={{
                  fontSize: '14px',
                  fontWeight: 600,
                  color: '#334155',
                  marginBottom: '16px',
                }}>
                  Try asking:
                </p>
                <div style={{ display: 'grid', gap: '12px' }}>
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
                        padding: '16px 20px',
                        background: 'white',
                        borderRadius: '12px',
                        border: '1px solid #e2e8f0',
                        textAlign: 'left',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                        boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#93c5fd'
                        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)'
                        e.currentTarget.style.transform = 'translateY(-2px)'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#e2e8f0'
                        e.currentTarget.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)'
                        e.currentTarget.style.transform = 'translateY(0)'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'start', gap: '12px' }}>
                        <span style={{ fontSize: '18px', opacity: 0.6 }}>💡</span>
                        <p style={{
                          fontSize: '14px',
                          color: '#334155',
                          margin: 0,
                          lineHeight: '1.5',
                          flex: 1,
                        }}>
                          {prompt}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {messages.map((msg, idx) => (
              <div
                key={msg.id}
                style={{
                  display: 'flex',
                  gap: '16px',
                  flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                  animation: 'fadeIn 0.3s ease-out',
                  animationFillMode: 'both',
                  animationDelay: `${idx * 0.05}s`,
                }}
              >
                <div style={{
                  flexShrink: 0,
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 600,
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
                  background: msg.role === 'user'
                    ? 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)'
                    : 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)',
                  color: msg.role === 'user' ? 'white' : '#475569',
                  border: msg.role === 'user' ? 'none' : '2px solid white',
                }}>
                  {msg.role === 'user' ? 'You' : 'AI'}
                </div>
                
                <div style={{
                  flex: 1,
                  maxWidth: '75%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}>
                  <div
                    style={{
                      borderRadius: '18px',
                      padding: '14px 18px',
                      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                      background: msg.role === 'user'
                        ? 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)'
                        : 'white',
                      color: msg.role === 'user' ? 'white' : '#1e293b',
                      borderTopLeftRadius: msg.role === 'user' ? '18px' : '4px',
                      borderTopRightRadius: msg.role === 'user' ? '4px' : '18px',
                      border: msg.role === 'user' ? 'none' : '1px solid #f1f5f9',
                    }}
                  >
                    <div style={{
                      fontSize: '14px',
                      lineHeight: '1.6',
                      whiteSpace: 'pre-wrap',
                      wordWrap: 'break-word',
                    }}>
                      {msg.content}
                    </div>
                    
                    {msg.citations && msg.citations.length > 0 && (
                      <div style={{
                        marginTop: '16px',
                        paddingTop: '12px',
                        borderTop: `1px solid ${msg.role === 'user' ? 'rgba(255, 255, 255, 0.2)' : '#e2e8f0'}`,
                      }}>
                        <div style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          marginBottom: '8px',
                          opacity: msg.role === 'user' ? 0.9 : 0.7,
                        }}>
                          📚 Sources
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {msg.citations.map((cite, citeIdx) => {
                            const colors = getSourceColor(cite.source, msg.role === 'user')
                            return (
                              <a
                                key={citeIdx}
                                href={cite.ref}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  display: 'block',
                                  fontSize: '12px',
                                  borderRadius: '8px',
                                  padding: '10px 12px',
                                  border: `1px solid ${colors.border}`,
                                  background: colors.bg,
                                  color: colors.text,
                                  textDecoration: 'none',
                                  transition: 'all 0.2s ease',
                                }}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.transform = 'translateY(-2px)'
                                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)'
                                  e.currentTarget.style.background = colors.hover
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.transform = 'translateY(0)'
                                  e.currentTarget.style.boxShadow = 'none'
                                  e.currentTarget.style.background = colors.bg
                                }}
                              >
                                <div style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '8px',
                                  marginBottom: '4px',
                                }}>
                                  <span style={{ fontSize: '16px' }}>{getSourceIcon(cite.source)}</span>
                                  <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                                    {cite.source}
                                  </span>
                                  {cite.confidence !== undefined && (
                                    <span style={{
                                      marginLeft: 'auto',
                                      fontSize: '10px',
                                      padding: '2px 8px',
                                      borderRadius: '12px',
                                      background: msg.role === 'user' 
                                        ? 'rgba(255, 255, 255, 0.2)' 
                                        : '#e2e8f0',
                                      color: msg.role === 'user' ? 'white' : '#475569',
                                    }}>
                                      {Math.round(cite.confidence * 100)}%
                                    </span>
                                  )}
                                </div>
                                <div style={{
                                  overflow: 'hidden',
                                  textOverflow: 'ellipsis',
                                  whiteSpace: 'nowrap',
                                  opacity: msg.role === 'user' ? 0.8 : 0.7,
                                }}>
                                  {cite.title}
                                </div>
                                {cite.ref && (
                                  <div style={{
                                    fontSize: '11px',
                                    marginTop: '4px',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                    opacity: msg.role === 'user' ? 0.6 : 0.5,
                                  }}>
                                    {cite.ref}
                                  </div>
                                )}
                              </a>
                            )
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  <div style={{
                    fontSize: '11px',
                    paddingLeft: '4px',
                    color: msg.role === 'user' ? '#64748b' : '#94a3b8',
                  }}>
                    {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>
            ))}
            
            {loading && (
              <div style={{ display: 'flex', gap: '16px', animation: 'fadeIn 0.3s ease-out' }}>
                <div style={{
                  flexShrink: 0,
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#475569',
                  border: '2px solid white',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
                }}>
                  AI
                </div>
                <div style={{ flex: 1, maxWidth: '75%' }}>
                  <div style={{
                    background: 'white',
                    borderRadius: '18px',
                    borderRadiusTopLeft: '4px',
                    padding: '16px 18px',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
                    border: '1px solid #f1f5f9',
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background: '#3b82f6',
                          animation: 'bounce 1.4s ease-in-out infinite',
                        }}></div>
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background: '#3b82f6',
                          animation: 'bounce 1.4s ease-in-out infinite',
                          animationDelay: '0.2s',
                        }}></div>
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          background: '#3b82f6',
                          animation: 'bounce 1.4s ease-in-out infinite',
                          animationDelay: '0.4s',
                        }}></div>
                      </div>
                      <span style={{ fontSize: '13px', color: '#64748b' }}>Thinking...</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div style={{
        background: 'rgba(255, 255, 255, 0.85)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        borderTop: '1px solid rgba(226, 232, 240, 0.5)',
        boxShadow: '0 -4px 12px rgba(0, 0, 0, 0.05)',
      }}>
        <div style={{ maxWidth: '896px', margin: '0 auto', padding: '16px' }}>
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
                    fontSize: '12px',
                    fontWeight: 500,
                    background: '#f1f5f9',
                    color: '#475569',
                    borderRadius: '16px',
                    border: '1px solid #e2e8f0',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#e2e8f0'
                    e.currentTarget.style.transform = 'scale(1.05)'
                    e.currentTarget.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = '#f1f5f9'
                    e.currentTarget.style.transform = 'scale(1)'
                    e.currentTarget.style.boxShadow = 'none'
                  }}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}
          
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
            <div style={{ flex: 1, position: 'relative' }}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything about your Notion docs or Git code..."
                rows={1}
                style={{
                  width: '100%',
                  padding: '14px 16px',
                  paddingRight: input.trim() ? '120px' : '16px',
                  background: 'white',
                  border: '1px solid #cbd5e1',
                  borderRadius: '12px',
                  fontSize: '14px',
                  fontFamily: 'inherit',
                  resize: 'none',
                  outline: 'none',
                  boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
                  transition: 'all 0.2s ease',
                  minHeight: '48px',
                  maxHeight: '120px',
                }}
                onFocus={(e) => {
                  e.currentTarget.style.borderColor = '#3b82f6'
                  e.currentTarget.style.boxShadow = '0 0 0 3px rgba(59, 130, 246, 0.1)'
                }}
                onBlur={(e) => {
                  e.currentTarget.style.borderColor = '#cbd5e1'
                  e.currentTarget.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.1)'
                }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = 'auto'
                  target.style.height = `${Math.min(target.scrollHeight, 120)}px`
                }}
              />
              {input.trim() && (
                <div style={{
                  position: 'absolute',
                  right: '16px',
                  bottom: '14px',
                  fontSize: '11px',
                  color: '#94a3b8',
                }}>
                  Press Enter to send
                </div>
              )}
            </div>
            <button
              onClick={sendMessage}
              disabled={!input.trim() || loading}
              style={{
                padding: '14px 24px',
                borderRadius: '12px',
                fontSize: '14px',
                fontWeight: 600,
                border: 'none',
                cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s ease',
                boxShadow: input.trim() && !loading 
                  ? '0 4px 12px rgba(59, 130, 246, 0.3)' 
                  : 'none',
                background: input.trim() && !loading
                  ? 'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)'
                  : '#cbd5e1',
                color: 'white',
              }}
              onMouseEnter={(e) => {
                if (input.trim() && !loading) {
                  e.currentTarget.style.transform = 'scale(1.05)'
                  e.currentTarget.style.boxShadow = '0 6px 16px rgba(59, 130, 246, 0.4)'
                }
              }}
              onMouseLeave={(e) => {
                if (input.trim() && !loading) {
                  e.currentTarget.style.transform = 'scale(1)'
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(59, 130, 246, 0.3)'
                }
              }}
              onMouseDown={(e) => {
                if (input.trim() && !loading) {
                  e.currentTarget.style.transform = 'scale(0.95)'
                }
              }}
              onMouseUp={(e) => {
                if (input.trim() && !loading) {
                  e.currentTarget.style.transform = 'scale(1.05)'
                }
              }}
            >
              {loading ? (
                <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    width: '14px',
                    height: '14px',
                    border: '2px solid white',
                    borderTopColor: 'transparent',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                    display: 'inline-block',
                  }}></span>
                  Sending...
                </span>
              ) : (
                'Send'
              )}
            </button>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        
        @keyframes pulse-slow {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.7;
          }
        }
        
        @keyframes bounce {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-6px);
          }
        }
        
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </div>
  )
}
