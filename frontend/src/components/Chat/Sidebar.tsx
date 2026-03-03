import { Plus, MessageSquare, LogOut, User, Trash2, Edit2, Check, Settings } from 'lucide-react'
import { useState } from 'react'
import type { Thread } from '../../hooks/useChat'
import { useAuth } from '../../context/AuthContext'

export type SidebarProps = {
  threads: Thread[]
  activeThreadId: string | null
  onSelectThread: (id: string | null) => void
  onDeleteThread: (id: string) => void
  onRenameThread: (id: string, title: string) => void
  onNewChat: () => void
  onOpenSettings: () => void
  isLoading?: boolean
}

export function Sidebar({
  threads,
  activeThreadId,
  onSelectThread,
  onDeleteThread,
  onRenameThread,
  onNewChat,
  onOpenSettings,
  isLoading
}: SidebarProps) {
  const { user, logout } = useAuth();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredThreads = (threads || []).filter(t =>
    t.title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const groupedThreads = {
    today: filteredThreads.filter(t => {
      const dateStr = t.created_at || t.createdAt;
      const date = new Date(dateStr || Date.now());
      const today = new Date();
      return date.toDateString() === today.toDateString();
    }),
    yesterday: filteredThreads.filter(t => {
      const dateStr = t.created_at || t.createdAt;
      const date = new Date(dateStr || Date.now());
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      return date.toDateString() === yesterday.toDateString();
    }),
    older: filteredThreads.filter(t => {
      const dateStr = t.created_at || t.createdAt;
      const date = new Date(dateStr || Date.now());
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      return date < yesterday && date.toDateString() !== yesterday.toDateString();
    })
  };

  const handleStartEdit = (e: React.MouseEvent, thread: Thread) => {
    e.stopPropagation();
    setEditingId(thread.id);
    setEditTitle(thread.title);
  };

  const handleSaveEdit = (e?: React.FormEvent | React.MouseEvent) => {
    e?.preventDefault();
    if (editingId && editTitle.trim()) {
      onRenameThread(editingId, editTitle.trim());
    }
    setEditingId(null);
  };

  const handleCancelEdit = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingId(null);
  };

  const renderThreadItem = (thread: Thread) => (
    <div
      key={thread.id}
      className={`group relative flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-300 cursor-pointer border border-transparent ${activeThreadId === thread.id
        ? 'bg-indigo-600/20 text-white border-indigo-500/30 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1)]'
        : 'text-slate-300 hover:bg-slate-800/60 hover:text-slate-100 hover:border-slate-700/50'
        }`}
      onClick={() => onSelectThread(thread.id)}
    >
      <MessageSquare className={`h-4 w-4 shrink-0 transition-colors ${activeThreadId === thread.id ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-400'}`} />

      {editingId === thread.id ? (
        <form
          onSubmit={handleSaveEdit}
          className="flex-1 flex items-center gap-1 min-w-0"
          onClick={(e) => e.stopPropagation()}
        >
          <input
            autoFocus
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            className="flex-1 bg-slate-700 text-white text-sm px-2 py-0.5 rounded-lg outline-none w-full border border-blue-500/30"
            onKeyDown={(e) => {
              if (e.key === 'Escape') handleCancelEdit();
            }}
          />
          <button
            type="submit"
            className="p-1 hover:bg-slate-600 rounded-md text-emerald-400"
          >
            <Check className="h-3.5 w-3.5" />
          </button>
        </form>
      ) : (
        <>
          <span className="flex-1 truncate text-[14px] font-bold tracking-tight font-playfair group-hover:text-white transition-colors">
            {thread.title || 'Untitled Chat'}
          </span>

          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              onClick={(e) => handleStartEdit(e, thread)}
              className="p-1.5 hover:bg-slate-700 rounded-lg transition-all text-slate-500 hover:text-blue-400"
              title="Rename"
            >
              <Edit2 className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteThread(thread.id);
              }}
              className="p-1.5 hover:bg-slate-700 rounded-lg transition-all text-slate-500 hover:text-rose-400"
              title="Delete"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </>
      )}
    </div>
  );

  return (
    <aside className="hidden md:flex md:w-64 glass-sidebar text-slate-100 flex-col h-screen overflow-hidden">
      {/* Top Section: New Chat Button */}
      <div className="p-4 space-y-4">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-3 px-4 py-3.5 rounded-2xl bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 border border-indigo-500/50 hover:border-indigo-400 transition-all duration-300 text-white text-sm font-semibold shadow-[0_0_20px_rgba(79,70,229,0.2)] hover:shadow-[0_0_25px_rgba(79,70,229,0.4)] active:scale-[0.98]"
        >
          <Plus className="h-5 w-5" />
          <span>New Chat</span>
        </button>

        {/* Search Bar */}
        <div className="relative group">
          <input
            type="text"
            placeholder="Tìm kiếm hội thoại..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-800/40 border border-slate-700/50 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder:text-slate-500 outline-none focus:border-indigo-500/50 focus:bg-slate-800/60 transition-all pl-10"
          />
          <MessageSquare className="absolute left-3.5 top-3 h-4 w-4 text-slate-500 group-focus-within:text-indigo-400 transition-colors" />
        </div>
      </div>

      {/* Middle Section: Chat History Grouped */}
      <div className="flex-1 overflow-y-auto px-2 space-y-6 py-2 custom-scrollbar">
        {isLoading ? (
          <div className="px-4 py-2 space-y-3">
            <div className="h-4 bg-slate-800/50 rounded-full animate-pulse w-3/4"></div>
            <div className="h-4 bg-slate-800/50 rounded-full animate-pulse w-1/2"></div>
            <div className="h-4 bg-slate-800/50 rounded-full animate-pulse w-2/3"></div>
          </div>
        ) : filteredThreads.length === 0 ? (
          <p className="px-4 text-xs text-slate-600 italic">No history found</p>
        ) : (
          <>
            {groupedThreads.today.length > 0 && (
              <div>
                <h3 className="px-4 text-[11px] font-bold text-indigo-400 uppercase tracking-[0.2em] mb-3 font-playfair">Hôm nay</h3>
                <div className="space-y-1">{groupedThreads.today.map(renderThreadItem)}</div>
              </div>
            )}
            {groupedThreads.yesterday.length > 0 && (
              <div>
                <h3 className="px-4 text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-3 font-playfair">Hôm qua</h3>
                <div className="space-y-1">{groupedThreads.yesterday.map(renderThreadItem)}</div>
              </div>
            )}
            {groupedThreads.older.length > 0 && (
              <div>
                <h3 className="px-4 text-[11px] font-bold text-slate-400 uppercase tracking-[0.2em] mb-3 font-playfair">Trước đó</h3>
                <div className="space-y-1">{groupedThreads.older.map(renderThreadItem)}</div>
              </div>
            )}
          </>
        )}
      </div>

      {/* Bottom Section: User Profile & Quick Actions */}
      <div className="p-4 border-t border-slate-800/50 space-y-3 bg-gradient-to-t from-[#0a0f1d] to-transparent">

        <div className="flex items-center gap-3 px-3 py-3 rounded-xl bg-slate-800/40 border border-slate-700/50 hover:border-slate-600/50 transition-colors">
          <div className="h-9 w-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg ring-2 ring-slate-800">
            {user?.name ? (
              <span className="text-sm font-bold text-white uppercase">{user.name[0]}</span>
            ) : (
              <User className="h-5 w-5 text-white" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-200 truncate leading-tight">{user?.name || 'Brotex User'}</p>
            <p className="text-[11px] text-slate-400 truncate mt-0.5 font-medium">{user?.email || 'user@brotex.com'}</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={onOpenSettings}
              className="p-2 hover:bg-slate-700/60 rounded-lg transition-colors text-slate-400 hover:text-indigo-400"
              title="Settings"
            >
              <Settings className="h-4 w-4" />
            </button>
            <button
              onClick={logout}
              className="p-2 hover:bg-slate-700/60 rounded-lg transition-colors text-slate-400 hover:text-rose-400"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </aside>
  )
}
