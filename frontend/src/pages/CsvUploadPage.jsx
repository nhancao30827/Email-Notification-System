import { useMemo, useState } from 'react'

import ErrorMessage from '../components/ErrorMessage'
import SectionCard from '../components/SectionCard'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { enqueueCsvTask, fileToBase64 } from '../services/deliveryService'

export default function CsvUploadPage({ token, initialCampaignId, onTaskQueued }) {
  const [campaignId, setCampaignId] = useState(initialCampaignId || '')
  const [file, setFile] = useState(null)
  const [successMessage, setSuccessMessage] = useState('')

  const { loading, error, run } = useAsyncAction()

  const isDisabled = useMemo(() => {
    return loading || !token.trim() || !campaignId.trim() || !file
  }, [loading, token, campaignId, file])

  async function handleSubmit(event) {
    event.preventDefault()
    setSuccessMessage('')

    const base64 = await fileToBase64(file)

    const response = await run(() =>
      enqueueCsvTask({
        campaignId: campaignId.trim(),
        csvBase64: base64,
        token,
      }),
    )

    setSuccessMessage(`Task queued: ${response.task_id}`)
    onTaskQueued(response.task_id)
  }

  return (
    <SectionCard
      title="CSV Upload"
      description="Upload recipients CSV with email and name columns. The file is converted to base64 and sent to the backend task endpoint."
    >
      <form className="stack-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="upload-campaign-id">Campaign ID</label>
        <input
          id="upload-campaign-id"
          type="text"
          value={campaignId}
          onChange={(event) => setCampaignId(event.target.value)}
          placeholder="Paste campaign UUID"
          required
        />

        <label htmlFor="recipient-csv">Recipient CSV</label>
        <input
          id="recipient-csv"
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
          required
        />

        <button type="submit" disabled={isDisabled}>
          {loading ? 'Uploading...' : 'Upload CSV and Queue Task'}
        </button>

        <ErrorMessage message={error} />
        {successMessage ? <p className="success-message">{successMessage}</p> : null}
      </form>
    </SectionCard>
  )
}
