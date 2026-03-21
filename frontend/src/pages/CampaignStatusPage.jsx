import { useMemo, useState } from 'react'

import ErrorMessage from '../components/ErrorMessage'
import SectionCard from '../components/SectionCard'
import StatusTable from '../components/StatusTable'
import { useTaskStatusPolling } from '../hooks/useTaskStatusPolling'

export default function CampaignStatusPage({ token, initialTaskId }) {
  const [taskInput, setTaskInput] = useState(initialTaskId || '')
  const [activeTaskId, setActiveTaskId] = useState(initialTaskId || '')

  const enabled = useMemo(() => {
    return Boolean(activeTaskId && token.trim())
  }, [activeTaskId, token])

  const { data, loading, error, isPolling, refresh } = useTaskStatusPolling({
    taskId: activeTaskId,
    token,
    enabled,
    intervalMs: 3000,
  })

  function handleTrack(event) {
    event.preventDefault()
    setActiveTaskId(taskInput.trim())
  }

  return (
    <SectionCard
      title="Campaign Status"
      description="Track CSV processing and delivery counters. Status refreshes automatically every 3 seconds."
    >
      <form className="inline-form" onSubmit={handleTrack}>
        <input
          type="text"
          value={taskInput}
          onChange={(event) => setTaskInput(event.target.value)}
          placeholder="Paste task ID"
          required
        />
        <button type="submit" disabled={!taskInput.trim() || !token.trim()}>
          Track Task
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => void refresh()}
          disabled={!activeTaskId || loading || !token.trim()}
        >
          Refresh Now
        </button>
      </form>

      <ErrorMessage message={error} />

      {!activeTaskId ? <p className="hint">Enter a task ID to start polling.</p> : null}

      {activeTaskId ? (
        <div className="status-block">
          <p>
            <strong>Task:</strong> {activeTaskId}
          </p>
          <p>
            <strong>State:</strong> {data?.state || (loading ? 'LOADING' : 'PENDING')}
          </p>
          <p>
            <strong>Status:</strong> {data?.status || 'pending'}
          </p>
          <p>
            <strong>Polling:</strong> {isPolling ? 'running' : 'stopped'}
          </p>

          <StatusTable metrics={data} />

          {data?.error ? <p className="error-message">{data.error}</p> : null}
        </div>
      ) : null}
    </SectionCard>
  )
}
