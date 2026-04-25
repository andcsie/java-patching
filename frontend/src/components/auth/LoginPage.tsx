import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { GitBranch, Key, Lock } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'
import LoginForm from './LoginForm'
import SSHLogin from './SSHLogin'

export default function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const [authMethod, setAuthMethod] = useState<'password' | 'ssh'>('password')

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <div className="flex justify-center">
            <GitBranch className="h-16 w-16 text-blue-500" />
          </div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-white">
            Java Patching
          </h2>
          <p className="mt-2 text-center text-sm text-gray-400">
            JDK Upgrade Impact Analyzer
          </p>
        </div>

        {/* Auth Method Toggle */}
        <div className="flex justify-center space-x-4">
          <button
            onClick={() => setAuthMethod('password')}
            className={`flex items-center px-4 py-2 rounded-md ${
              authMethod === 'password'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Lock className="h-4 w-4 mr-2" />
            Password
          </button>
          <button
            onClick={() => setAuthMethod('ssh')}
            className={`flex items-center px-4 py-2 rounded-md ${
              authMethod === 'ssh'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            <Key className="h-4 w-4 mr-2" />
            SSH Key
          </button>
        </div>

        <div className="card">
          {authMethod === 'password' ? (
            <LoginForm isLoading={isLoading} />
          ) : (
            <SSHLogin isLoading={isLoading} />
          )}
        </div>
      </div>
    </div>
  )
}
