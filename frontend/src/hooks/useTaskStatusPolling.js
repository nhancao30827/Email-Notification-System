import { useCallback, useEffect, useRef, useState } from 'react'

import { getCsvTaskStatus } from '../services/deliveryService'

const TERMINAL_STATES = new Set(['SUCCESS', 'FAILURE'])

export function useTaskStatusPolling({ taskId, token, intervalMs = 3000, enabled = true }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isPolling, setIsPolling] = useState(false)

  const timerRef = useRef(null)

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
    setIsPolling(false)
  }, [])

  const fetchStatus = useCallback(async () => {
    if (!taskId) {
      return
    }

    setLoading(true)
    setError('')

    try {
      const status = await getCsvTaskStatus({ taskId, token })
      setData(status)

      if (TERMINAL_STATES.has(status.state)) {
        stopPolling()
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch task status')
      stopPolling()
    } finally {
      setLoading(false)
    }
  }, [taskId, token, stopPolling])

  useEffect(() => {
    stopPolling()

    if (!enabled || !taskId) {
      setData(null)
      setError('')
      return
    }

    void fetchStatus()

    timerRef.current = window.setInterval(() => {
      void fetchStatus()
    }, intervalMs)

    setIsPolling(true)

    return () => {
      stopPolling()
    }
  }, [enabled, taskId, intervalMs, fetchStatus, stopPolling])

  return {
    data,
    loading,
    error,
    isPolling,
    refresh: fetchStatus,
    stopPolling,
  }
}
