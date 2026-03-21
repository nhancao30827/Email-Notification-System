import { apiRequest } from './apiClient'

export function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()

    reader.onload = () => {
      if (typeof reader.result !== 'string' || !reader.result) {
        reject(new Error('Failed to read the CSV file.'))
        return
      }
      resolve(reader.result)
    }

    reader.onerror = () => {
      reject(new Error('Could not convert file to base64.'))
    }

    reader.readAsDataURL(file)
  })
}

export async function enqueueCsvTask({ campaignId, csvBase64, token }) {
  return apiRequest(`/campaigns/${campaignId}/deliveries/process-csv`, {
    method: 'POST',
    token,
    body: {
      csv_content: csvBase64,
    },
  })
}

export async function getCsvTaskStatus({ taskId, token }) {
  return apiRequest(`/campaigns/deliveries/tasks/${taskId}`, {
    method: 'GET',
    token,
  })
}
