import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Settings2 } from 'lucide-react'
import { useLLMProviders } from '../../hooks/useLLMProvider'
import { agentApi } from '../../services/api'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: providers } = useLLMProviders()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await agentApi.chat({
        content: input,
        provider: selectedProvider || undefined,
      })

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.data.content,
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      toast.error('Failed to get response')
      // Remove the user message on error
      setMessages((prev) => prev.filter((m) => m.id !== userMessage.id))
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Assistant</h1>
          <p className="text-gray-400">
            Ask questions about JDK upgrades and get migration help
          </p>
        </div>

        <button
          onClick={() => setShowSettings(!showSettings)}
          className="btn btn-secondary flex items-center"
        >
          <Settings2 className="h-4 w-4 mr-2" />
          Settings
        </button>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="card mb-4">
          <h3 className="text-lg font-medium text-white mb-3">Chat Settings</h3>
          <div className="flex items-center space-x-4">
            <label className="text-gray-300">LLM Provider:</label>
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              className="input w-48"
            >
              <option value="">Default</option>
              {providers?.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto card mb-4">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <Bot className="h-16 w-16 text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-400">
                Start a conversation
              </h3>
              <p className="text-gray-500 mt-2 max-w-md">
                Ask me about JDK version changes, migration strategies,
                deprecated APIs, or code fixes for your Java projects.
              </p>
              <div className="mt-6 space-y-2">
                <p className="text-sm text-gray-500">Example questions:</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {[
                    'What changed between JDK 11.0.18 and 11.0.22?',
                    'How do I migrate from SecurityManager?',
                    'Explain the TLS 1.0/1.1 deprecation',
                  ].map((q) => (
                    <button
                      key={q}
                      onClick={() => setInput(q)}
                      className="px-3 py-1 bg-gray-700 rounded-full text-sm text-gray-300 hover:bg-gray-600"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`flex max-w-[80%] ${
                    message.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                  }`}
                >
                  <div
                    className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
                      message.role === 'user' ? 'bg-blue-600 ml-3' : 'bg-gray-600 mr-3'
                    }`}
                  >
                    {message.role === 'user' ? (
                      <User className="h-5 w-5 text-white" />
                    ) : (
                      <Bot className="h-5 w-5 text-white" />
                    )}
                  </div>

                  <div
                    className={`rounded-lg px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-200'
                    }`}
                  >
                    {message.role === 'assistant' ? (
                      <div className="prose prose-invert prose-sm max-w-none">
                        <ReactMarkdown>{message.content}</ReactMarkdown>
                      </div>
                    ) : (
                      <p>{message.content}</p>
                    )}
                    <span className="block text-xs opacity-50 mt-2">
                      {message.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="flex">
                  <div className="flex-shrink-0 h-8 w-8 rounded-full bg-gray-600 flex items-center justify-center mr-3">
                    <Bot className="h-5 w-5 text-white" />
                  </div>
                  <div className="bg-gray-700 rounded-lg px-4 py-3">
                    <div className="flex space-x-2">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: '0.1s' }}
                      ></div>
                      <div
                        className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: '0.2s' }}
                      ></div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex space-x-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about JDK changes, migration strategies, or code fixes..."
          className="input flex-1 resize-none"
          rows={2}
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="btn btn-primary px-6 self-end"
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  )
}
