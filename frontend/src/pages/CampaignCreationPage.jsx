import { useMemo, useState } from 'react'

import ErrorMessage from '../components/ErrorMessage'
import SectionCard from '../components/SectionCard'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { createCampaign } from '../services/campaignService'

export default function CampaignCreationPage({ token, onCreated }) {
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const { loading, error, run } = useAsyncAction()

  const isDisabled = useMemo(() => {
    return loading || !subject.trim() || !body.trim() || !token.trim()
  }, [loading, subject, body, token])

  async function handleSubmit(event) {
    event.preventDefault()
    setSuccessMessage('')

    const result = await run(() =>
      createCampaign({
        subject: subject.trim(),
        body: body.trim(),
        token,
      }),
    )

    setSuccessMessage(`Campaign created: ${result.id}`)
    onCreated(result)
  }

  return (
    <SectionCard
      title="Campaign Creation"
      description="Create a campaign first, then upload recipient CSV for this campaign."
    >
      <form className="stack-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="campaign-subject">Subject</label>
        <input
          id="campaign-subject"
          type="text"
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
          placeholder="Welcome to our March update"
          required
        />

        <label htmlFor="campaign-body">Body</label>
        <textarea
          id="campaign-body"
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Hello, this is our latest product update..."
          rows={7}
          required
        />

        <button type="submit" disabled={isDisabled}>
          {loading ? 'Creating...' : 'Create Campaign'}
        </button>

        <ErrorMessage message={error} />
        {successMessage ? <p className="success-message">{successMessage}</p> : null}
      </form>
    </SectionCard>
  )
}
