import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import clsx from 'clsx'
import { Copy, Check, ThumbsUp, ThumbsDown, RotateCcw } from 'lucide-react'

export type UIProfile = 'CONSUMER' | 'EXPERT' | 'AUDIT'

export type MessageBubbleProps = {
  role: 'user' | 'assistant'
  content: string
  profile?: UIProfile
  decision_trace?: any
}

const DEFAULT_PROFILE: UIProfile = 'CONSUMER'

const renderQualLevel = (level: string, profile: UIProfile) => {
  const l = level.toUpperCase()
  const base = 'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider shadow-sm'

  if (profile === 'CONSUMER') {
    if (l.includes('HIGH')) return '🟢 Cao'
    if (l.includes('MEDIUM')) return '🟡 Trung bình'
    if (l.includes('LOW')) return '🔴 Thấp'
    return level
  }

  if (profile === 'EXPERT') {
    if (l.includes('HIGH')) return <span className={`${base} bg-emerald-100 text-emerald-700 border border-emerald-200`}>HIGH | {level}</span>
    if (l.includes('MEDIUM')) return <span className={`${base} bg-amber-100 text-amber-700 border border-amber-200`}>MED | {level}</span>
    if (l.includes('LOW')) return <span className={`${base} bg-rose-100 text-rose-700 border border-rose-200`}>LOW | {level}</span>
    return level
  }

  if (profile === 'AUDIT') {
    const bar = (w: string, c: string) => (
      <div className="w-20 h-2 bg-gray-200 rounded-sm overflow-hidden inline-block align-middle ml-2 border border-gray-300">
        <div className={`h-full ${c} transition-all duration-500`} style={{ width: w }}></div>
      </div>
    )
    if (l.includes('HIGH')) return <span className="text-[10px] font-mono text-gray-500">[{l}] {bar('90%', 'bg-emerald-500')}</span>
    if (l.includes('MEDIUM')) return <span className="text-[10px] font-mono text-gray-500">[{l}] {bar('50%', 'bg-amber-500')}</span>
    if (l.includes('LOW')) return <span className="text-[10px] font-mono text-gray-500">[{l}] {bar('20%', 'bg-rose-500')}</span>
    return level
  }

  return level
}

export function MessageBubble({ role, content, profile = DEFAULT_PROFILE, decision_trace }: MessageBubbleProps) {
  const isUser = role === 'user'
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'like' | 'dislike' | null>(null)

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Presentation Contract Guard: Force block separation for key markers & Strip inner metadata
  let processedContent = content
  if (!isUser) {
    // 1. Strip raw robotic strings if they leak
    processedContent = processedContent
      .replace(/STATUS MARKERS:.*?\n/gi, '')
      .replace(/\[QUAL_LEVEL:[A-Z]+\]/g, (match) => {
        // Only strip if not in a table line (heuristic: starts with |)
        // Actually, we refine the markdown component to handle this, 
        // but stripping here for non-table text is safer.
        return match;
      })

    // 2. Force newline before markers if clumped
    processedContent = processedContent
      .replace(/([^\n])(📌)/g, '$1\n\n$2')
      .replace(/([^\n])(## 🧠)/g, '$1\n\n$2')
      .replace(/([^\n])(## 📊)/g, '$1\n\n$2')
      .replace(/([^\n])(## 📌)/g, '$1\n\n$2')
      .replace(/([^\n])(## 💡)/g, '$1\n\n$2')
      .replace(/([^\n])(🧠)/g, '$1\n\n$2')
      .replace(/([^\n])(📊)/g, '$1\n\n$2')
  }

  const renderConfidenceBadge = () => {
    if (!decision_trace?.confidence_level) return null;
    const conf = decision_trace.confidence_level;
    const isHigh = conf === 'HIGH';

    // For standard CONSUMER profile, we remove the text label entirely as requested.
    // We only show a visual cue for EXPERT/AUDIT users.
    if (profile === 'CONSUMER') return null;

    return (
      <div className={clsx(
        "w-2 h-2 rounded-full mb-2 border shadow-sm",
        isHigh ? "bg-emerald-500 border-emerald-600" : "bg-amber-500 border-amber-600"
      )} title={isHigh ? 'High Confidence' : 'Partial Confidence'} />
    );
  }

  return (
    <div className={clsx('w-full group/msg relative mb-8', isUser ? 'flex justify-end' : '')}>
      <div
        className={clsx(
          'transition-all duration-300 relative',
          isUser
            ? 'max-w-[80%] rounded-[1.2rem] px-5 py-3.5 text-[15px] leading-relaxed bg-[#2563eb] dark:bg-[#3b82f6] text-white shadow-md hover:shadow-lg transition-all font-sans'
            : 'w-full px-0 py-6 text-slate-900 dark:text-slate-100 dark:bg-transparent border-none',
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap font-medium tracking-tight leading-snug">{content}</p>
        ) : (
          <div className="prose prose-slate dark:prose-invert max-w-none text-[16px]
            prose-p:my-2 prose-p:leading-relaxed
            prose-li:my-1 
            prose-headings:mt-6 prose-headings:mb-3 prose-headings:font-bold prose-headings:font-playfair
            prose-code:text-slate-700 dark:prose-code:text-slate-300 prose-code:bg-slate-100 dark:prose-code:bg-slate-700/50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:text-xs prose-code:font-mono
            prose-table:border-collapse prose-table:border prose-table:border-slate-200 dark:prose-table:border-slate-700
            prose-th:border prose-th:border-slate-200 dark:prose-th:border-slate-700 prose-th:bg-slate-50 dark:prose-th:bg-slate-800/80 prose-th:px-3 prose-th:py-2.5 prose-th:text-xs prose-th:uppercase prose-th:tracking-wider
            prose-td:border prose-td:border-slate-200 dark:prose-td:border-slate-700 prose-td:px-3 prose-td:py-2.5">
            {renderConfidenceBadge()}
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => {
                  if (typeof children === 'string') {
                    // Match [QUAL_LEVEL:X] pattern
                    const parts = children.split(/(\[QUAL_LEVEL:[A-Z]+\])/g)
                    return (
                      <p className="my-1.5 leading-relaxed">
                        {parts.map((part, i) => {
                          if (part.startsWith('[QUAL_LEVEL:')) {
                            const level = part.replace('[QUAL_LEVEL:', '').replace(']', '')
                            return <React.Fragment key={i}>{renderQualLevel(level, profile)}</React.Fragment>
                          }
                          return part
                        })}
                      </p>
                    )
                  }
                  return <p className="my-1.5">{children}</p>
                },
                td: ({ children }) => {
                  // Recursively handle string patterns inside table cells
                  const renderNested = (node: any): any => {
                    if (typeof node === 'string') {
                      const parts = node.split(/(\[QUAL_LEVEL:[A-Z]+\])/g)
                      return parts.map((part, i) => {
                        if (part.startsWith('[QUAL_LEVEL:')) {
                          const level = part.replace('[QUAL_LEVEL:', '').replace(']', '')
                          return <React.Fragment key={i}>{renderQualLevel(level, profile)}</React.Fragment>
                        }
                        return part
                      })
                    }
                    if (Array.isArray(node)) return node.map(renderNested)
                    return node
                  }

                  return (
                    <td className="border border-slate-200 dark:border-slate-700 px-3 py-2.5">
                      {renderNested(children)}
                    </td>
                  )
                }
              }}
            >
              {processedContent}
            </ReactMarkdown>
          </div>
        )}

        {/* Floating Toolbar on Hover */}
        <div className={clsx(
          "absolute -bottom-4 opacity-0 group-hover/msg:opacity-100 translate-y-2 group-hover/msg:translate-y-0 transition-all duration-300 flex items-center gap-1 p-1 rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-800 z-10",
          isUser ? "right-6" : "left-6"
        )}>
          <button
            onClick={handleCopy}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors text-slate-500 dark:text-slate-400 hover:text-blue-500"
            title="Copy"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
          </button>

          {!isUser && (
            <>
              <div className="w-px h-3 bg-slate-200 dark:bg-slate-800 mx-1"></div>
              <button
                onClick={() => setFeedback('like')}
                className={clsx(
                  "p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors",
                  feedback === 'like' ? "text-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 shadow-inner" : "text-slate-500 dark:text-slate-400 hover:text-emerald-500"
                )}
                title="Good response"
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={() => setFeedback('dislike')}
                className={clsx(
                  "p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors",
                  feedback === 'dislike' ? "text-rose-500 bg-rose-50 dark:bg-rose-500/10 shadow-inner" : "text-slate-500 dark:text-slate-400 hover:text-rose-500"
                )}
                title="Bad response"
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>
              <div className="w-px h-3 bg-slate-200 dark:bg-slate-800 mx-1"></div>
              <button
                className="p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl transition-colors text-slate-500 dark:text-slate-400 hover:text-indigo-500"
                title="Regenerate"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            </>
          )}
        </div>

        {profile === 'AUDIT' && decision_trace && role === 'assistant' && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <details className="group">
              <summary className="text-[10px] font-bold text-gray-400 uppercase tracking-widest cursor-pointer hover:text-indigo-500 transition-colors flex items-center gap-2 outline-none">
                <span className="w-2 h-2 rounded-full bg-indigo-400 group-open:animate-ping"></span>
                Decision Trace Contract v2
              </summary>
              <div className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-100 font-mono text-[11px] text-gray-600 overflow-x-auto whitespace-pre">
                {JSON.stringify(decision_trace, null, 2)}
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  )
}
