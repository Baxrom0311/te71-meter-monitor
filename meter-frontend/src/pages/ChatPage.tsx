import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { RootLayout } from '@/components/layout/RootLayout'
import { MessageSquare, Trash, Send, Sparkles, Bot } from 'lucide-react'
import { getTokenFromStorage, removeTokenFromStorage } from '@/lib/auth'
import { API_BASE_URL } from '@/lib/env'
import { notify } from '@/lib/toast'
import clsx from 'clsx'

interface Message {
  role: 'user' | 'model'
  content: string
  thoughts?: string
}

export default function ChatPage() {
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [history, setHistory] = useState<Message[]>([])
  const [provider, setProvider] = useState('gemini')
  const [isLoading, setIsLoading] = useState(false)
  const [thoughts, setThoughts] = useState('')
  const [partialResponse, setPartialResponse] = useState('')
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [userIsScrollingUp, setUserIsScrollingUp] = useState(false)

  // Quick Prompts list
  const quickPrompts = [
    { text: '📊 Tizim holati', prompt: 'Tizimning umumiy holatini ko\'rsat: nechta qurilma online, ogohlantirishlar bormi?' },
    { text: '🚨 Faol ogohlantirishlar', prompt: 'Hozirgi tizimdagi barcha faol ogohlantirishlarni ro\'yxatini chiqar' },
    { text: '🏢 Binolar va qurilmalar', prompt: 'Barcha binolar va ularga ulangan qurilmalar ro\'yxatini chiqar' },
    { text: '💡 Elektr sarfi tahlili', prompt: 'Qaysi binolar eng ko\'p elektr sarflamoqda? So\'nggi 30 kunlik ma\'lumot' },
    { text: '💧 Suv bosimi holati', prompt: 'Suv bosim qurilmalari holatini ko\'rsat, anomaliyalar bormi?' },
    { text: '🔌 Oflayn qurilmalar', prompt: 'Qaysi qurilmalar hozirda oflayn? Ro\'yxat va oxirgi ko\'ringan vaqtlari' },
  ]

  // Detect user scroll to prevent force scroll-down during streaming
  const handleScroll = () => {
    const el = messagesContainerRef.current
    if (!el) return
    const threshold = 40
    const isAtBottom = el.scrollHeight - el.clientHeight - el.scrollTop < threshold
    setUserIsScrollingUp(!isAtBottom)
  }

  const scrollToBottom = () => {
    if (!userIsScrollingUp && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [history, partialResponse, thoughts])

  // Auto resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [message])

  const handleQuickPrompt = (promptText: string) => {
    setMessage(promptText)
    submitMessage(promptText)
  }

  const submitMessage = async (textToSend: string) => {
    if (!textToSend.trim() || isLoading) return

    // Add User message
    const newMsg: Message = { role: 'user', content: textToSend }
    setHistory((prev) => [...prev, newMsg])
    setMessage('')
    setIsLoading(true)
    setThoughts('')
    setPartialResponse('')
    setUserIsScrollingUp(false)

    try {
      const token = getTokenFromStorage()
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: textToSend,
          history: history.map(h => ({ role: h.role, content: h.content })),
          provider: provider
        })
      })

      if (!response.ok) {
        let message = `HTTP ${response.status}`
        try {
          const body = await response.json()
          if (typeof body.detail === 'string') message = body.detail
          else if (typeof body.message === 'string') message = body.message
        } catch {
          // Non-JSON error responses still get a status-specific message below.
        }

        if (response.status === 401) {
          removeTokenFromStorage()
          window.sessionStorage.setItem(
            'meter-toast',
            JSON.stringify({
              type: 'warning',
              title: 'Sessiya tugadi',
              message: 'Xavfsizlik uchun qaytadan login qiling.',
            }),
          )
          navigate('/login', { replace: true })
          return
        }

        if (response.status === 403) {
          notify({ type: 'warning', title: 'Ruxsat yetarli emas', message })
        } else if (response.status >= 500) {
          notify({ type: 'error', title: 'Server bilan muammo', message })
        }

        throw new Error(message)
      }

      if (!response.body) throw new Error('Response body is empty')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let accumulatedThoughts = ''
      let accumulatedResponse = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.slice(6).trim()
            if (dataStr === '[DONE]') continue
            try {
              const data = JSON.parse(dataStr)
              if (data.type === 'THOUGHT') {
                accumulatedThoughts += (accumulatedThoughts ? '\n' : '') + data.content
                setThoughts(accumulatedThoughts)
              } else if (data.type === 'FINAL_RESPONSE') {
                accumulatedResponse += data.content
                setPartialResponse(accumulatedResponse)
              }
            } catch (e) {
              console.error('SSE parsing error', e)
            }
          }
        }
      }

      // Add to final history
      setHistory((prev) => [
        ...prev,
        { role: 'model', content: accumulatedResponse, thoughts: accumulatedThoughts }
      ])
      setThoughts('')
      setPartialResponse('')

    } catch (err: any) {
      console.error(err)
      setHistory((prev) => [
        ...prev,
        { role: 'model', content: `Xatolik yuz berdi: ${err.message}` }
      ])
    } finally {
      setIsLoading(false)
    }
  }

  // Parse custom simple markdown (tables, bold, headings)
  const parseMarkdown = (text: string) => {
    let html = text
    html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    html = html.replace(/^### (.*?)$/gm, '<h6 class="text-blue-400 font-bold mt-3 mb-1 text-sm">$1</h6>')
    html = html.replace(/^## (.*?)$/gm, '<h5 class="text-blue-400 font-bold mt-4 mb-2 text-base">$1</h5>')
    html = html.replace(/^# (.*?)$/gm, '<h4 class="text-blue-400 font-bold mt-5 mb-2 text-lg">$1</h4>')
    html = html.replace(/^\* (.*?)$/gm, '<li class="ml-4 list-disc">$1</li>')
    html = html.replace(/^- (.*?)$/gm, '<li class="ml-4 list-disc">$1</li>')

    // Table parser
    html = html.replace(/\|(.+)\|/g, (match) => {
      const cells = match.split('|').slice(1, -1)
      const isHeader = cells.every(c => c.trim().startsWith('---'))
      if (isHeader) return ''
      const tdType = match.includes('**') ? 'th' : 'td'
      const cellHtml = cells.map(c => `<${tdType} class="p-3 border border-gray-300 dark:border-gray-700 align-top">${c.trim()}</${tdType}>`).join('')
      return `<tr class="border-b border-gray-300 dark:border-gray-700 transition">${cellHtml}</tr>`
    })
    // Wrap tables
    html = html.replace(/((?:<tr class="border-b border-gray-300 dark:border-gray-700">[\s\S]*?<\/tr>)+)/g, '<div class="overflow-x-auto my-4 rounded-xl border border-gray-200 dark:border-gray-700 shadow-md"><table class="w-full text-sm border-collapse text-left">$1</table></div>')

    // Code block parser
    html = html.replace(/```([\s\S]*?)```/g, '<pre class="bg-gray-100 dark:bg-gray-950 text-gray-800 dark:text-gray-200 p-4 rounded-lg my-3 font-mono text-xs overflow-x-auto border border-gray-200 dark:border-gray-800 shadow-inner">$1</pre>')
    html = html.replace(/`(.*?)`/g, '<code class="bg-gray-200 dark:bg-gray-800 px-1.5 py-0.5 rounded font-mono text-blue-600 dark:text-blue-400 text-xs">$1</code>')
    html = html.replace(/\n/g, '<br>')
    return <div dangerouslySetInnerHTML={{ __html: html }} />
  }

  const handleClear = () => {
    setHistory([])
    setThoughts('')
    setPartialResponse('')
  }

  return (
    <RootLayout>
      <div className="space-y-6 flex flex-col h-[calc(100vh-80px)]">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <MessageSquare className="w-8 h-8 text-blue-500" />
            <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">AI Yordamchi</h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleClear}
              className="flex items-center gap-2 px-3.5 py-2 bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-700 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white rounded-lg transition-all text-sm border border-gray-200 dark:border-gray-700 font-semibold shadow-sm"
            >
              <Trash className="w-4 h-4" />
              Tozalash
            </button>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="px-3.5 py-2 bg-white/80 dark:bg-gray-950/60 border border-gray-200 dark:border-gray-700/50 rounded-lg text-gray-900 dark:text-gray-100 focus:outline-none focus:border-blue-500 text-sm font-semibold shadow-sm backdrop-blur-sm"
            >
              <option value="gemini">Gemini 2.5 Flash</option>
              <option value="deepseek">DeepSeek Chat</option>
            </select>
          </div>
        </div>

        {/* Chat Box */}
        <div className="flex-1 glass-card rounded-xl flex flex-col overflow-hidden shadow-2xl min-h-[400px]">
          {/* Messages Area */}
          <div
            ref={messagesContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-6 space-y-4"
          >
            {history.length === 0 && !partialResponse && !thoughts && (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 animate-fade-in">
                <Sparkles className="w-12 h-12 text-blue-500/40 mb-3 animate-pulse" />
                <p className="text-gray-400 font-medium max-w-sm">
                  Salom! Men elektr, suv va gaz monitoringi tizimingizning AI yordamchisiman. Qurilmalar holati, ogohlantirishlar, sarflar tahlili va boshqaruv bo'yicha savol yozing.
                </p>
              </div>
            )}

            {history.map((msg, idx) => (
              <div
                key={idx}
                className={clsx(
                  'flex flex-col gap-1.5 max-w-[85%] animate-fade-in',
                  msg.role === 'user' ? 'self-end ml-auto' : 'self-start mr-auto'
                )}
              >
                {msg.thoughts && (
                  <div className="msg-thoughts text-xs border-l-2 border-yellow-500 pl-3 italic text-yellow-500 bg-yellow-500/5 p-2.5 rounded-lg flex gap-1.5">
                    <Bot className="w-3.5 h-3.5 shrink-0 text-yellow-500" />
                    <span>{msg.thoughts}</span>
                  </div>
                )}
                <div
                  className={clsx(
                    'px-4.5 py-3 rounded-xl text-sm leading-relaxed shadow-md',
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-tr-none'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 rounded-tl-none'
                  )}
                >
                  {parseMarkdown(msg.content)}
                </div>
              </div>
            ))}

            {/* SSE Streaming thoughts / response */}
            {(thoughts || partialResponse) && (
              <div className="flex flex-col gap-1.5 max-w-[85%] self-start mr-auto animate-pulse">
                {thoughts && (
                  <div className="msg-thoughts text-xs border-l-2 border-yellow-500 pl-3 italic text-yellow-500 bg-yellow-500/5 p-2.5 rounded-lg flex gap-1.5">
                    <Bot className="w-3.5 h-3.5 shrink-0 text-yellow-500 animate-spin" />
                    <span>{thoughts}</span>
                  </div>
                )}
                {partialResponse && (
                  <div className="px-4.5 py-3 rounded-xl text-sm leading-relaxed shadow-md bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 rounded-tl-none">
                    {parseMarkdown(partialResponse)}
                  </div>
                )}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Typing indicator */}
          {isLoading && !partialResponse && (
            <div className="px-6 py-2.5 text-xs text-yellow-500 bg-yellow-500/5 border-t border-gray-200 dark:border-gray-800 flex items-center gap-2">
              <span className="animate-bounce">●</span>
              <span className="animate-bounce delay-100">●</span>
              <span className="animate-bounce delay-200">●</span>
              AI fikrlamoqda va o'lchov ko'rsatkichlarini tahlil qilmoqda...
            </div>
          )}

          {/* Input Area */}
          <div className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/40 p-4 space-y-3">
            {/* Quick Suggestions */}
            {history.length === 0 && (
              <div className="flex flex-wrap gap-2 animate-fade-in">
                {quickPrompts.map((p, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleQuickPrompt(p.prompt)}
                    className="text-xs px-3.5 py-1.5 bg-gray-100/80 dark:bg-gray-950/50 border border-gray-200 dark:border-gray-700/50 hover:border-blue-500 rounded-full text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-all duration-300 hover:scale-105 active:scale-95 shadow-sm backdrop-blur-sm"
                  >
                    {p.text}
                  </button>
                ))}
              </div>
            )}

            <div className="flex items-end gap-3">
              <textarea
                ref={textareaRef}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    submitMessage(message)
                  }
                }}
                placeholder="Savol yozing (masalan: 'Qaysi qurilmalar offline?', '3-bino suv bosimi qanday?', 'Relay o\'chir')..."
                rows={1}
                className="flex-1 bg-white/80 dark:bg-gray-950/60 border border-gray-200 dark:border-gray-700/50 rounded-lg px-4 py-3 text-sm text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-blue-500 transition max-h-[120px] min-h-[48px] resize-none backdrop-blur-sm"
              />
              <button
                disabled={isLoading || !message.trim()}
                onClick={() => submitMessage(message)}
                className="h-12 w-12 flex items-center justify-center bg-blue-500 hover:bg-blue-600 disabled:bg-gray-100 dark:disabled:bg-gray-800 disabled:text-gray-400 dark:disabled:text-gray-600 text-white rounded-lg transition-all hover:scale-105 active:scale-95 shrink-0 shadow-lg"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </RootLayout>
  )
}
