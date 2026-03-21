import { useMemo, useState } from 'react'

import CampaignCreationPage from './pages/CampaignCreationPage'
import CampaignStatusPage from './pages/CampaignStatusPage'
import CsvUploadPage from './pages/CsvUploadPage'
import LoginPage from './pages/LoginPage'
import { logout } from './services/authService'
import { API_BASE_URL } from './services/apiClient'

const PAGES = {
  login: 'login',
  campaign: 'campaign',
  upload: 'upload',
  status: 'status',
}

function App() {
  const [activePage, setActivePage] = useState(() => {
    const storedToken = window.localStorage.getItem('access_token') || ''
    return storedToken.trim() ? PAGES.campaign : PAGES.login
  })
  const [token, setToken] = useState(() => window.localStorage.getItem('access_token') || '')
  const [refreshToken, setRefreshToken] = useState(() => window.localStorage.getItem('refresh_token') || '')
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [authMessage, setAuthMessage] = useState('')
  const [campaignId, setCampaignId] = useState('')
  const [taskId, setTaskId] = useState('')

  const tokenReady = useMemo(() => Boolean(token.trim()), [token])

  function handleLoginSuccess(tokens) {
    setToken(tokens.access_token)
    setRefreshToken(tokens.refresh_token)
    setAuthMessage('')
    window.localStorage.setItem('access_token', tokens.access_token)
    window.localStorage.setItem('refresh_token', tokens.refresh_token)
    setActivePage(PAGES.campaign)
  }

  async function handleLogout() {
    setIsLoggingOut(true)
    setAuthMessage('')

    try {
      if (token.trim() && refreshToken.trim()) {
        await logout({
          token: token.trim(),
          refreshToken: refreshToken.trim(),
        })
      }
    } catch (error) {
      setAuthMessage(
        error instanceof Error
          ? `Token cleared locally. Logout API returned: ${error.message}`
          : 'Token cleared locally. Logout API returned an unexpected error.',
      )
    }

    setToken('')
    setRefreshToken('')
    window.localStorage.removeItem('access_token')
    window.localStorage.removeItem('refresh_token')
    setCampaignId('')
    setTaskId('')
    setActivePage(PAGES.login)
    setIsLoggingOut(false)
  }

  function handleCampaignCreated(campaign) {
    setCampaignId(campaign.id)
    setActivePage(PAGES.upload)
  }

  function handleTaskQueued(queuedTaskId) {
    setTaskId(queuedTaskId)
    setActivePage(PAGES.status)
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>Email Campaign Frontend</h1>
        <p className="subtle">Backend API: {API_BASE_URL}</p>
      </header>

      <section className="token-panel">
        {tokenReady ? (
          <>
            <p className="success-message">Signed in and ready for API calls.</p>
            <div className="button-row">
              <button type="button" className="secondary" onClick={() => setActivePage(PAGES.login)}>
                Account
              </button>
              <button type="button" onClick={() => void handleLogout()} disabled={isLoggingOut}>
                {isLoggingOut ? 'Signing out...' : 'Sign Out'}
              </button>
            </div>
          </>
        ) : (
          <p className="warning-message">Please sign in to create campaigns and send deliveries.</p>
        )}

        {authMessage ? <p className="warning-message">{authMessage}</p> : null}
      </section>

      <nav className="tab-nav" aria-label="Pages">
        <button
          type="button"
          className={activePage === PAGES.login ? 'active' : ''}
          onClick={() => setActivePage(PAGES.login)}
        >
          Login
        </button>
        <button
          type="button"
          className={activePage === PAGES.campaign ? 'active' : ''}
          onClick={() => setActivePage(PAGES.campaign)}
          disabled={!tokenReady}
        >
          Campaign Creation
        </button>
        <button
          type="button"
          className={activePage === PAGES.upload ? 'active' : ''}
          onClick={() => setActivePage(PAGES.upload)}
          disabled={!tokenReady}
        >
          CSV Upload
        </button>
        <button
          type="button"
          className={activePage === PAGES.status ? 'active' : ''}
          onClick={() => setActivePage(PAGES.status)}
          disabled={!tokenReady}
        >
          Campaign Status
        </button>
      </nav>

      {campaignId ? <p className="hint">Current campaign: {campaignId}</p> : null}
      {taskId ? <p className="hint">Current task: {taskId}</p> : null}

      {activePage === PAGES.login ? <LoginPage token={token} onLogin={handleLoginSuccess} /> : null}

      {activePage === PAGES.campaign ? (
        <CampaignCreationPage token={token} onCreated={handleCampaignCreated} />
      ) : null}

      {activePage === PAGES.upload ? (
        <CsvUploadPage token={token} initialCampaignId={campaignId} onTaskQueued={handleTaskQueued} />
      ) : null}

      {activePage === PAGES.status ? <CampaignStatusPage token={token} initialTaskId={taskId} /> : null}
    </main>
  )
}

export default App
