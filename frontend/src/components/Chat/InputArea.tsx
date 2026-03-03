import { useCallback, useEffect, useRef, useState } from 'react'
import { Send } from 'lucide-react'

export type InputAreaProps = {
  onSend: (text: string) => void | Promise<void>
  onStop?: () => void
  disabled?: boolean
}

export function InputArea({ onSend, onStop, disabled }: InputAreaProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const autoResize = useCallback(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = '0px'
    const next = Math.min(el.scrollHeight, 160)
    el.style.height = `${next}px`
  }, [])

  useEffect(() => {
    autoResize()
  }, [value, autoResize])

  const submit = useCallback(async () => {
    const text = value.trim()
    if (!text || disabled) return
    await onSend(text)
    setValue('')
  }, [value, disabled, onSend])

  return (
    <div className="sticky bottom-0 w-full pt-4">
      <div className="floating-capsule relative group/input">
        <textarea
          ref={textareaRef}
          value={value}
          disabled={disabled}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void submit()
            }
          }}
          placeholder={disabled ? 'Brotex AI đang suy nghĩ...' : 'Hỏi trợ lý Brotex AI...'}
          className="w-full resize-none bg-transparent text-[15px] leading-relaxed text-slate-900 dark:text-slate-100 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none disabled:opacity-60 pr-12 min-h-[24px]"
          rows={1}
        />

        <div className="absolute right-3 bottom-3 flex items-center gap-2">
          {disabled && onStop && (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400 hover:bg-rose-50 dark:hover:bg-rose-900/20 hover:text-rose-500 transition-all duration-300"
              title="Stop generating"
            >
              <div className="h-3 w-3 bg-current rounded-sm" />
            </button>
          )}
          <button
            type="button"
            onClick={() => void submit()}
            disabled={disabled || value.trim().length === 0}
            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-blue-600 dark:bg-blue-500 text-white shadow-lg shadow-blue-500/20 transition-all duration-300 disabled:bg-slate-200 dark:disabled:bg-slate-800 disabled:text-slate-400 dark:disabled:text-slate-600 disabled:shadow-none hover:bg-blue-500 dark:hover:bg-blue-400 active:scale-90"
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
