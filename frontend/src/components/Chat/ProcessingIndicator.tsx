import { Loader2 } from 'lucide-react'

export type ProcessingIndicatorProps = {
  statusStep: 'idle' | 'queued' | 'processing' | 'answering'
  elapsedSeconds: number
}

const statusText: Record<'queued' | 'processing', string> = {
  queued: 'Đang chờ trong hàng đợi...',
  processing: 'AI đang nghiên cứu tài liệu & suy luận...',
}

export function ProcessingIndicator({ statusStep, elapsedSeconds }: ProcessingIndicatorProps) {
  const visible = statusStep !== 'idle' && statusStep !== 'answering'
  if (!visible) return null

  const text = statusStep === 'queued' ? statusText.queued : statusText.processing

  return (
    <div className="w-full flex justify-center py-4 animate-fade-in">
      <div className="flex items-center gap-4 rounded-2xl border border-slate-200/50 dark:border-slate-800/50 bg-white/50 dark:bg-slate-900/50 px-5 py-3.5 shadow-sm backdrop-blur-md animate-pulse">
        <div className="relative">
          <Loader2 className="h-5 w-5 animate-spin text-blue-600 dark:text-blue-500" />
          <div className="absolute inset-0 blur-sm bg-blue-400/20 dark:bg-blue-400/10 rounded-full animate-pulse"></div>
        </div>
        <div className="flex flex-col">
          <div className="text-sm font-bold text-slate-900 dark:text-slate-100 italic">{text}</div>
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-0.5">
            Thời gian: <span className="text-slate-900 dark:text-white">{elapsedSeconds}s</span>
          </div>
        </div>
      </div>
    </div>
  )
}

