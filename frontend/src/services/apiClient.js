const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

function buildUrl(path) {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path
  }

  const base = API_BASE_URL.replace(/\/$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${base}${normalizedPath}`
}

function buildErrorMessage(payload, status) {
  if (payload && typeof payload === 'object') {
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
    if (typeof payload.error === 'string') {
      return payload.error
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg || JSON.stringify(item)).join(', ')
    }
  }

  return `Request failed with status ${status}`
}

async function parseResponse(response) {
  if (response.status === 204) {
    return null
  }

  const text = await response.text()
  if (!text) {
    return null
  }

  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export async function apiRequest(path, options = {}) {
  const {
    method = 'GET',
    token,
    body,
    headers = {},
  } = options

  const requestHeaders = { ...headers }

  if (token) {
    requestHeaders.Authorization = `Bearer ${token}`
  }

  let requestBody = body
  if (body !== undefined && body !== null && !(body instanceof FormData)) {
    requestHeaders['Content-Type'] = 'application/json'
    requestBody = JSON.stringify(body)
  }

  const response = await fetch(buildUrl(path), {
    method,
    headers: requestHeaders,
    body: requestBody,
  })

  const payload = await parseResponse(response)

  if (!response.ok) {
    const error = new Error(buildErrorMessage(payload, response.status))
    error.status = response.status
    error.payload = payload
    throw error
  }

  return payload
}

export { API_BASE_URL }
