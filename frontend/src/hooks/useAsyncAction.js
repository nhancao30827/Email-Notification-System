import { useCallback, useState } from 'react'

export function useAsyncAction() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const run = useCallback(async (action) => {
    setLoading(true)
    setError('')

    try {
      return await action()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unexpected error')
      throw err
    } finally {
      setLoading(false)
    }
  }, [])

  return {
    loading,
    error,
    setError,
    run,
  }
}
