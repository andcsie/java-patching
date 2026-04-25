import { useState } from 'react'
import { useAuth } from '../../hooks/useAuth'

interface Props {
  isLoading: boolean
}

export default function SSHLogin({ isLoading }: Props) {
  const [username, setUsername] = useState('')
  const { handleSSHLogin, error, clearError } = useAuth()

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await handleSSHLogin(username)
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

      <div className="bg-blue-900/30 border border-blue-500/50 rounded-md p-4 text-sm text-blue-200">
        <p className="font-medium mb-2">SSH Key Authentication</p>
        <p>
          You'll be prompted to sign a challenge with your SSH private key.
          Make sure you've configured your public key in your account settings.
        </p>
      </div>

      <div>
        <label htmlFor="ssh-username" className="block text-sm font-medium text-gray-300">
          Username
        </label>
        <input
          id="ssh-username"
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
        <button
          type="submit"
          disabled={isLoading}
          className="btn btn-primary w-full"
        >
          {isLoading ? 'Authenticating...' : 'Sign in with SSH Key'}
        </button>
      </div>

      <div className="text-center text-sm text-gray-400">
        <p>Need to set up SSH authentication?</p>
        <p>Log in with password first and add your SSH key in settings.</p>
      </div>
    </form>
  )
}
