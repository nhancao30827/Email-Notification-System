import { useMemo, useState } from 'react'

import ErrorMessage from '../components/ErrorMessage'
import SectionCard from '../components/SectionCard'
import { useAsyncAction } from '../hooks/useAsyncAction'
import { login } from '../services/authService'

export default function LoginPage({ token, onLogin }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  const { loading, error, run } = useAsyncAction()

  const isDisabled = useMemo(() => {
    return loading || !email.trim() || !password.trim()
  }, [loading, email, password])

  async function handleSubmit(event) {
    event.preventDefault()

    const response = await run(() =>
      login({
        email: email.trim(),
        password,
      }),
    )

    setPassword('')
    onLogin(response)
  }

  return (
    <SectionCard
      title="Account Login"
      description="Sign in to get an access token for protected campaign and delivery API calls."
    >
      <form className="stack-form" onSubmit={(event) => void handleSubmit(event)}>
        <label htmlFor="login-email">Email</label>
        <input
          id="login-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
          autoComplete="email"
          required
        />

        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Enter your password"
          autoComplete="current-password"
          required
        />

        <button type="submit" disabled={isDisabled}>
          {loading ? 'Signing in...' : 'Sign In'}
        </button>

        <ErrorMessage message={error} />
        {token ? <p className="success-message">Session token is active on this device.</p> : null}
      </form>
    </SectionCard>
  )
}
