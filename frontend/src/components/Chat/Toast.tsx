import { useEffect, useState } from 'react'
import { AlertCircle, X } from 'lucide-react'

export type ToastProps = {
    message: string | null
    onDismiss?: () => void
    duration?: number
}

export function Toast({ message, onDismiss, duration = 5000 }: ToastProps) {
    const [visible, setVisible] = useState(false)

    useEffect(() => {
        if (message) {
            setVisible(true)
            const timer = setTimeout(() => {
                setVisible(false)
                setTimeout(() => onDismiss?.(), 300) // Wait for fade-out animation
            }, duration)
            return () => clearTimeout(timer)
        } else {
            setVisible(false)
        }
    }, [message, duration, onDismiss])

    if (!message) return null

    return (
        <div
            className={`fixed bottom-4 right-4 z-50 transition-all duration-300 ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
                }`}
        >
            <div className="flex items-start gap-3 max-w-md rounded-lg bg-red-50 border border-red-200 px-4 py-3 shadow-lg">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-red-800">Error</p>
                    <p className="text-sm text-red-700 mt-1">{message}</p>
                </div>
                {onDismiss && (
                    <button
                        onClick={() => {
                            setVisible(false)
                            setTimeout(() => onDismiss(), 300)
                        }}
                        className="text-red-600 hover:text-red-800 transition flex-shrink-0"
                        aria-label="Dismiss"
                    >
                        <X className="h-4 w-4" />
                    </button>
                )}
            </div>
        </div>
    )
}
