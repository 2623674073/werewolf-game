import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'

import { ApiError, clearToken, setToken, validateSession } from '../api/client'
import { useAuth } from '../auth/AuthContext'

export function LoginPage() {
  const { authenticated, login } = useAuth()
  const navigate = useNavigate()
  const [token, setTokenValue] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (authenticated) return <Navigate to="/games" replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    const value = token.trim()
    if (!value) return
    setSubmitting(true)
    setError('')
    setToken(value)
    try {
      await validateSession()
      login(value)
      navigate('/games', { replace: true })
    } catch (cause) {
      clearToken()
      setError(cause instanceof ApiError ? cause.message : '无法连接游戏服务')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <div className="mist mist-one" />
      <div className="mist mist-two" />
      <section className="login-hero">
        <span className="seal large">弈</span>
        <p className="eyebrow">AgentScope · 三国主题 AI 推演</p>
        <h1>群雄夜宴</h1>
        <p className="hero-subtitle">观六军暗涌，听群英辨忠奸</p>
      </section>
      <form className="login-card" onSubmit={submit}>
        <span className="eyebrow">进入司天台</span>
        <h2>验证观战令牌</h2>
        <p>令牌仅保存在当前浏览器会话，关闭标签页后自动清除。</p>
        <label>
          <span>APP API TOKEN</span>
          <input
            type="password"
            autoFocus
            autoComplete="current-password"
            placeholder="输入管理令牌"
            value={token}
            onChange={(event) => setTokenValue(event.target.value)}
          />
        </label>
        {error && <div className="form-error">{error}</div>}
        <button className="button primary wide" disabled={submitting || !token.trim()}>
          {submitting ? '正在验印…' : '持令入席'}
        </button>
      </form>
    </main>
  )
}
