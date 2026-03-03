import { useState } from 'react'
import { Menu } from 'lucide-react'
import type { ChatMessage, ChatStatusStep, Thread } from '../../hooks/useChat'
import { MessageList } from './MessageList'
import type { UIProfile } from './MessageBubble'
import { ProcessingIndicator } from './ProcessingIndicator'
import { InputArea } from './InputArea'
import { Sidebar } from './Sidebar'
import { Toast } from './Toast'

export type ChatLayoutProps = {
  messages: ChatMessage[]
  statusStep: ChatStatusStep
  elapsedSeconds: number
  isLoading: boolean
  error: string | null
  threads: Thread[]
  currentThreadId: string | null
  onSend: (text: string) => void | Promise<void>
  onStop?: () => void
  onSelectThread: (id: string | null) => void
  onDeleteThread: (id: string) => void
  onRenameThread: (id: string, title: string) => void
  onDismissError?: () => void
  profile?: UIProfile
}

import { SettingsModal } from './SettingsModal'
import { WelcomeScreen } from './WelcomeScreen'

export function ChatLayout({
  messages,
  statusStep,
  elapsedSeconds,
  isLoading,
  error,
  threads,
  currentThreadId,
  onSend,
  onStop,
  onSelectThread,
  onDeleteThread,
  onRenameThread,
  onDismissError,
  profile,
}: ChatLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)

  const showWelcome = messages.length === 0 && !isLoading

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden transition-colors duration-300">
      {/* Sidebar - Desktop */}
      <Sidebar
        threads={threads}
        activeThreadId={currentThreadId}
        onSelectThread={onSelectThread}
        onDeleteThread={onDeleteThread}
        onRenameThread={onRenameThread}
        onNewChat={() => onSelectThread(null)}
        onOpenSettings={() => setSettingsOpen(true)}
        isLoading={isLoading}
      />

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-40 md:hidden animate-fade-in"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="fixed inset-y-0 left-0 w-72 glass-sidebar text-slate-100 flex flex-col z-50 md:hidden animate-slide-up">
            <Sidebar
              threads={threads}
              activeThreadId={currentThreadId}
              onSelectThread={onSelectThread}
              onDeleteThread={onDeleteThread}
              onRenameThread={onRenameThread}
              onNewChat={() => {
                onSelectThread(null)
                setSidebarOpen(false)
              }}
              onOpenSettings={() => {
                setSettingsOpen(true)
                setSidebarOpen(false)
              }}
              isLoading={isLoading}
            />
          </aside>
        </>
      )}

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden relative textile-pattern">
        {/* Mobile Header */}
        <header className="md:hidden sticky top-0 z-10 border-b border-slate-200/50 dark:border-slate-800/50 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-all text-slate-600 dark:text-slate-400"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-sm font-bold text-slate-900 dark:text-white">Brotex AI</h1>
            <p className="text-[10px] font-medium text-slate-500 uppercase tracking-wider">Research & Development</p>
          </div>
        </header>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto pt-4 md:pt-8 scroll-smooth custom-scrollbar relative">
          <div className="mx-auto w-full max-w-[850px] px-4 md:px-6">
            {showWelcome ? (
              <WelcomeScreen onSelectPrompt={onSend} />
            ) : (
              <MessageList messages={messages} isLoading={isLoading} profile={profile} />
            )}
          </div>
        </div>

        {/* Processing Indicator */}
        <div className="mx-auto w-full max-w-[850px] px-4 md:px-6">
          <ProcessingIndicator statusStep={statusStep} elapsedSeconds={elapsedSeconds} />
        </div>

        {/* Input Area */}
        <div className="pb-8 pt-2">
          <div className="mx-auto w-full max-w-[850px] px-4 md:px-6">
            <InputArea onSend={onSend} onStop={onStop} disabled={isLoading} />
          </div>
          <p className="text-center text-[10px] text-slate-400 dark:text-slate-600 mt-4 px-4">
            Brotex AI có thể mắc lỗi. Hãy kiểm tra những thông tin quan trọng.
          </p>
        </div>
      </main>

      {/* Modals & Toasts */}
      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <Toast message={error} onDismiss={onDismissError} />
    </div>
  )
}
