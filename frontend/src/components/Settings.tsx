import { useAuth } from '../hooks/useAuth'
import { useDefaultLLMProvider } from '../hooks/useLLMProvider'

export default function Settings() {
  const { user } = useAuth()
  const { provider, setProvider, availableProviders } = useDefaultLLMProvider()

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-white mb-6">Settings</h1>

      {/* Account Info */}
      <div className="card mb-6">
        <h2 className="text-lg font-medium text-white mb-4">Account</h2>
        <div className="space-y-3">
          <div className="flex justify-between">
            <span className="text-gray-400">Username</span>
            <span className="text-white">{user?.username}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Email</span>
            <span className="text-white">{user?.email || 'Not set'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Auth Method</span>
            <span className="text-white capitalize">
              {user?.auth_method || 'Password'}
            </span>
          </div>
        </div>
      </div>

      {/* LLM Provider */}
      <div className="card mb-6">
        <h3 className="text-lg font-medium text-white mb-4">LLM Provider</h3>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-1">
            Default Provider
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="input w-full"
          >
            {availableProviders.map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
          <p className="mt-1 text-xs text-gray-500">
            Select which LLM provider to use by default for analysis and chat
          </p>
        </div>

        {availableProviders.length === 0 && (
          <div className="mt-4 bg-yellow-900/30 border border-yellow-500/50 rounded-md p-4">
            <p className="text-yellow-200 text-sm">
              No LLM providers are configured. Contact your administrator to set up
              API keys for OpenAI, Anthropic, Google, or Ollama.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
