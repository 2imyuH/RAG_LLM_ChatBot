import { useEffect, useRef } from 'react'
import type { ChatMessage } from '../../hooks/useChat'
import { MessageBubble, type UIProfile } from './MessageBubble'
import BotIcon from '../../assets/icon.svg'

export type MessageListProps = {
  messages: ChatMessage[]
  isLoading?: boolean
  profile?: UIProfile
}

export function MessageList({ messages, isLoading, profile }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement | null>(null)

  if (!messages || !Array.isArray(messages)) {
    return null
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, isLoading])

  return (
    <div className="flex-1 overflow-y-auto px-3 py-4">
      <div className="mx-auto w-full max-w-4xl space-y-3">
        {messages.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-600">
            Ask a question to start. Responses may take ~2–3 minutes due to the RAG pipeline.
          </div>
        ) : null}

        {messages.map((m) => (
          <MessageBubble
            key={m.id}
            role={m.role === 'assistant' ? 'assistant' : 'user'}
            content={m.content}
            profile={profile}
            decision_trace={m.role === 'assistant' ? m.decision_trace : undefined}
          />
        ))}

        {isLoading && (
          <div className="flex justify-start mb-4 animate-pulse">
            <div className="flex items-center bg-gray-100 dark:bg-gray-800 rounded-2xl px-4 py-3 shadow-sm border border-gray-200 dark:border-gray-700">
              <img
                src={BotIcon}
                alt="Thinking"
                className="w-5 h-5 mr-3 animate-spin-slow"
              />
              <span className="text-gray-500 text-sm font-medium">Thinking...</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

