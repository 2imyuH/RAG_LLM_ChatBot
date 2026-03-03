import { useCallback, useEffect, useRef, useState } from 'react'
import { io, Socket } from 'socket.io-client'
import api from '../api/api'

type Role = 'user' | 'assistant' | 'system'

export type ChatMessage = {
  id: string
  role: Role
  content: string
  decision_trace?: any
  createdAt: string
}

export type ChatStatusStep = 'idle' | 'queued' | 'processing' | 'answering'

export type Thread = {
  id: string
  title: string
  createdAt?: string
  created_at?: string
}

type ChatState = {
  messages: ChatMessage[]
  isLoading: boolean
  statusStep: ChatStatusStep
  currentJobId: string | null
  currentThreadId: string | null
  elapsedSeconds: number
  error: string | null
}

const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:5005'
const SOCKET_PATH = '/socket.io'

export function useChat() {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    statusStep: 'idle',
    currentJobId: null,
    currentThreadId: null,
    elapsedSeconds: 0,
    error: null,
  })

  const [threads, setThreads] = useState<Thread[]>([])
  const socketRef = useRef<Socket | null>(null)
  const timerRef = useRef<number | null>(null)

  const connectSocket = useCallback(() => {
    if (socketRef.current?.connected) {
      return socketRef.current
    }

    const socket = io(API_BASE_URL, {
      path: SOCKET_PATH,
      transports: ['websocket', 'polling'],
      autoConnect: true,
      auth: {
        token: localStorage.getItem('token')
      }
    })

    socket.on('connect', () => {
      console.log('[Socket] connected', socket.id)
    })

    socket.on('disconnect', (reason) => {
      console.log('[Socket] disconnected', reason)
    })

    socketRef.current = socket
    return socket
  }, [])

  const startTimer = useCallback(() => {
    if (timerRef.current != null) return
    const start = Date.now()
    timerRef.current = window.setInterval(() => {
      const elapsedMs = Date.now() - start
      setState((prev) => ({
        ...prev,
        elapsedSeconds: Math.floor(elapsedMs / 1000),
      }))
    }, 1000)
  }, [])

  const stopTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const fetchThreads = useCallback(async () => {
    try {
      const response = await api.get('/threads')
      // Extract from { threads: [...] } or handle array directly
      const data = response.data.threads || (Array.isArray(response.data) ? response.data : [])
      setThreads(data)
    } catch (err) {
      console.error('Failed to fetch threads', err)
      setThreads([])
    }
  }, [])

  const selectThread = useCallback(async (threadId: string | null) => {
    if (!threadId) {
      setState(prev => ({
        ...prev,
        currentThreadId: null,
        messages: [],
        statusStep: 'idle'
      }))
      return
    }

    try {
      setState(prev => ({ ...prev, isLoading: true, currentThreadId: threadId, messages: [] }))
      const response = await api.get(`/threads/${threadId}/messages`)
      // Harden data extraction
      const data = response.data.messages || (Array.isArray(response.data) ? response.data : [])
      setState(prev => ({
        ...prev,
        messages: data,
        isLoading: false,
        statusStep: 'idle'
      }))
    } catch (err: any) {
      console.error('Failed to load thread messages', err)
      setState(prev => ({
        ...prev,
        messages: [],
        isLoading: false,
        error: err.response?.data?.error || 'Failed to load thread messages'
      }))
    }
  }, [])

  const renameThread = useCallback(async (threadId: string, newTitle: string) => {
    try {
      await api.put(`/threads/${threadId}`, { title: newTitle })
      setThreads(prev => prev.map(t => t.id === threadId ? { ...t, title: newTitle } : t))
    } catch (err) {
      console.error('Failed to rename thread', err)
    }
  }, [])

  const deleteThread = useCallback(async (threadId: string) => {
    try {
      await api.delete(`/threads/${threadId}`)
      setThreads(prev => prev.filter(t => t.id !== threadId))
      if (state.currentThreadId === threadId) {
        selectThread(null)
      }
    } catch (err) {
      console.error('Failed to delete thread', err)
    }
  }, [state.currentThreadId, selectThread])

  // Initial load
  useEffect(() => {
    fetchThreads()
  }, [fetchThreads])

  // Socket listeners
  useEffect(() => {
    const socket = connectSocket()

    const handleJoined = () => {
      setState((prev) => ({ ...prev, statusStep: 'processing' }))
    }

    const handleComplete = (data: {
      jobId: string
      answer: string
      decision_trace?: any
      threadId: string
    }) => {
      setState((prev) => {
        if (prev.currentJobId !== data.jobId) return prev

        const assistantMessage: ChatMessage = {
          id: `assistant-${data.jobId}`,
          role: 'assistant',
          content: data.answer,
          decision_trace: data.decision_trace,
          createdAt: new Date().toISOString(),
        }

        return {
          ...prev,
          messages: [...prev.messages, assistantMessage],
          isLoading: false,
          statusStep: 'answering',
          currentThreadId: data.threadId || prev.currentThreadId
        }
      })
      if (data.threadId) fetchThreads()
      stopTimer()
    }

    const handleError = (data: { jobId: string; error: string }) => {
      setState((prev) => {
        if (prev.currentJobId !== data.jobId) return prev
        return {
          ...prev,
          isLoading: false,
          statusStep: 'idle',
          error: data.error,
        }
      })
      stopTimer()
    }

    socket.on('joined_job', handleJoined)
    socket.on('chat_complete', handleComplete)
    socket.on('chat_error', handleError)

    return () => {
      socket.off('joined_job', handleJoined)
      socket.off('chat_complete', handleComplete)
      socket.off('chat_error', handleError)
    }
  }, [connectSocket, stopTimer, fetchThreads])

  const sendMessage = useCallback(async (text: string) => {
    const query = text.trim()
    if (!query || state.isLoading) return

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: query,
      createdAt: new Date().toISOString(),
    }

    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
      statusStep: 'queued',
      error: null,
      elapsedSeconds: 0,
    }))

    try {
      console.log('[useChat] Sending message, threadId:', state.currentThreadId)
      const response = await api.post('/chat', {
        query,
        threadId: state.currentThreadId
      })

      const { jobId, threadId: newThreadId } = response.data
      setState((prev) => ({
        ...prev,
        currentJobId: jobId,
        currentThreadId: newThreadId || prev.currentThreadId
      }))

      // If this was a new thread, refresh the thread list
      if (!state.currentThreadId && newThreadId) {
        fetchThreads();
      }

      const socket = connectSocket()
      socket.emit('join_job', { jobId })
      startTimer()
    } catch (error: any) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        statusStep: 'idle',
        error: error.response?.data?.error || 'Failed to send message',
      }))
      stopTimer()
    }
  }, [connectSocket, startTimer, stopTimer, state.isLoading, state.currentThreadId])

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }))
  }, [])

  const stopGeneration = useCallback(() => {
    if (!state.currentJobId) return

    setState(prev => ({
      ...prev,
      isLoading: false,
      statusStep: 'idle',
      currentJobId: null
    }))

    stopTimer()

    // Optionally emit abort to socket
    if (socketRef.current) {
      socketRef.current.emit('abort_job', { jobId: state.currentJobId })
    }
  }, [state.currentJobId, stopTimer])

  return {
    ...state,
    threads,
    sendMessage,
    stopGeneration,
    clearError,
    selectThread,
    deleteThread,
    createNewChat: () => selectThread(null),
    refreshThreads: fetchThreads,
    renameThread,
  }
}

