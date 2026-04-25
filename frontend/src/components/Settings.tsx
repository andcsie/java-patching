import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useLLMProviders, useDefaultLLMProvider } from '../hooks/useLLMProvider'
import AuthMethodSwitch from './auth/AuthMethodSwitch'
import toast from 'react-hot-toast'

export default function Settings() {
  const { user, updateSSHKey } = useAuth()
  const { provider, setProvider, availableProviders } = useDefaultLLMProvider()
  const [sshKey, setSSHKey] = useState('')
  const [isUpdating, setIsUpdating] = useState(false)

  const handleUpdateSSHKey = async () => {
    if (!sshKey.trim()) {
      toast.error('Please enter an SSH public key')
      return
    }

    setIsUpdating(true)
    try {
      await updateSSHKey(sshKey)
      setSSHKey('')
    } finally {
      setIsUpdating(false)
    }
  }

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
        </div>
      </div>

      {/* Auth Method Switch */}
      <div className="mb-6">
        <AuthMethodSwitch />
      </div>

      {/* SSH Key Setup */}
      <div className="card mb-6">
        <h3 className="text-lg font-medium text-white mb-4">SSH Key</h3>

        {user?.has_ssh_auth ? (
          <div className="bg-green-900/30 border border-green-500/50 rounded-md p-4 mb-4">
            <p className="text-green-200">SSH key is configured</p>
          </div>
        ) : (
          <div className="bg-yellow-900/30 border border-yellow-500/50 rounded-md p-4 mb-4">
            <p className="text-yellow-200">No SSH key configured</p>
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-1">
              SSH Public Key
            </label>
            <textarea
              value={sshKey}
              onChange={(e) => setSSHKey(e.target.value)}
              className="input"
              rows={4}
              placeholder="ssh-ed25519 AAAA... or ssh-rsa AAAA..."
            />
            <p className="mt-1 text-xs text-gray-500">
              Paste your public SSH key (usually found in ~/.ssh/id_ed25519.pub or
              ~/.ssh/id_rsa.pub)
            </p>
          </div>

          <button
            onClick={handleUpdateSSHKey}
            disabled={isUpdating}
            className="btn btn-primary"
          >
            {isUpdating ? 'Updating...' : user?.has_ssh_auth ? 'Update Key' : 'Add Key'}
          </button>
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
