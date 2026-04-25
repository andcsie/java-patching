import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'

interface Props {
  isLoading: boolean
}

export default function LoginForm({ isLoading }: Props) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { handleLogin, error, clearError } = useAuth()

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await handleLogin(username, password)
  }

  return (
    <form className="space-y-6" onSubmit={onSubmit}>
      {error && (
        <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded relative">
          {error}
          <button
            className="absolute top-0 right-0 px-4 py-3"
            onClick={clearError}
          >
            &times;
          </button>
        </div>
      )}

      <div>
        <label htmlFor="username" className="block text-sm font-medium text-gray-300">
          Username
        </label>
        <input
          id="username"
          name="username"
          type="text"
          required
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="input mt-1"
          placeholder="Enter your username"
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium text-gray-300">
          Password
        </label>
        <input
          id="password"
          name="password"
          type="password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="input mt-1"
          placeholder="Enter your password"
        />
      </div>

      <div>
        <button
          type="submit"
          disabled={isLoading}
          className="btn btn-primary w-full"
        >
          {isLoading ? 'Signing in...' : 'Sign in'}
        </button>
      </div>
    </form>
  )
}
