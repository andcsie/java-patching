import { Key, Lock } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

export default function AuthMethodSwitch() {
  const { user, switchAuthMethod } = useAuth()

  if (!user) return null

  return (
    <div className="card">
      <h3 className="text-lg font-medium text-white mb-4">Authentication Method</h3>

      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
          <div className="flex items-center">
            <Lock className="h-5 w-5 text-gray-400 mr-3" />
            <div>
              <p className="text-white font-medium">Password</p>
              <p className="text-sm text-gray-400">
                {user.has_password_auth ? 'Configured' : 'Not configured'}
              </p>
            </div>
          </div>
          <button
            onClick={() => switchAuthMethod('password')}
            disabled={!user.has_password_auth || user.preferred_auth_method === 'password'}
            className={`px-4 py-2 rounded-md ${
              user.preferred_auth_method === 'password'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {user.preferred_auth_method === 'password' ? 'Active' : 'Use'}
          </button>
        </div>

        <div className="flex items-center justify-between p-4 bg-gray-700 rounded-lg">
          <div className="flex items-center">
            <Key className="h-5 w-5 text-gray-400 mr-3" />
            <div>
              <p className="text-white font-medium">SSH Key</p>
              <p className="text-sm text-gray-400">
                {user.has_ssh_auth ? 'Configured' : 'Not configured'}
              </p>
            </div>
          </div>
          <button
            onClick={() => switchAuthMethod('ssh_key')}
            disabled={!user.has_ssh_auth || user.preferred_auth_method === 'ssh_key'}
            className={`px-4 py-2 rounded-md ${
              user.preferred_auth_method === 'ssh_key'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-600 text-gray-300 hover:bg-gray-500'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {user.preferred_auth_method === 'ssh_key' ? 'Active' : 'Use'}
          </button>
        </div>
      </div>
    </div>
  )
}
