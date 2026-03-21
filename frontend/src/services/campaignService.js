import { apiRequest } from './apiClient'

function buildCampaignName(subject) {
  const trimmed = subject.trim()
  const normalized = trimmed.length > 40 ? trimmed.slice(0, 40) : trimmed
  const suffix = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  return `${normalized || 'Campaign'}-${suffix}`
}

export async function createCampaign({ subject, body, token }) {
  return apiRequest('/campaigns', {
    method: 'POST',
    token,
    body: {
      name: buildCampaignName(subject),
      subject,
      body,
    },
  })
}
