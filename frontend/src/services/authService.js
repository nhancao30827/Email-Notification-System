import { apiRequest } from './apiClient'

export function login({ email, password }) {
  return apiRequest('/auth/login', {
    method: 'POST',
    body: {
      email,
      password,
    },
  })
}

export function logout({ token, refreshToken }) {
  if (!refreshToken) {
    return Promise.resolve(null)
  }

  return apiRequest('/auth/logout', {
    method: 'POST',
    token,
    body: {
      refresh_token: refreshToken,
    },
  })
}
