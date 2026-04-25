import { Github, Chrome } from 'lucide-react'

interface SSOLoginProps {
  isLoading?: boolean
}

export default function SSOLogin({ isLoading }: SSOLoginProps) {
  const handleSSOLogin = (provider: string) => {
    // Redirect to backend SSO endpoint
    window.location.href = `/api/auth/sso/${provider}`
  }

  return (
    <div className="space-y-4">
      <p className="text-center text-gray-400 text-sm mb-6">
        Sign in with your organization account
      </p>

      <button
        onClick={() => handleSSOLogin('google')}
        disabled={isLoading}
        className="w-full flex items-center justify-center px-4 py-3 border border-gray-600 rounded-md shadow-sm bg-gray-700 hover:bg-gray-600 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Chrome className="h-5 w-5 mr-3" />
        Continue with Google
      </button>

      <button
        onClick={() => handleSSOLogin('github')}
        disabled={isLoading}
        className="w-full flex items-center justify-center px-4 py-3 border border-gray-600 rounded-md shadow-sm bg-gray-700 hover:bg-gray-600 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <Github className="h-5 w-5 mr-3" />
        Continue with GitHub
      </button>

      <button
        onClick={() => handleSSOLogin('microsoft')}
        disabled={isLoading}
        className="w-full flex items-center justify-center px-4 py-3 border border-gray-600 rounded-md shadow-sm bg-gray-700 hover:bg-gray-600 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        <svg className="h-5 w-5 mr-3" viewBox="0 0 23 23" fill="currentColor">
          <path d="M0 0h11v11H0zM12 0h11v11H12zM0 12h11v11H0zM12 12h11v11H12z" />
        </svg>
        Continue with Microsoft
      </button>

      <div className="relative my-6">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-600"></div>
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="px-2 bg-gray-800 text-gray-400">Or use SAML</span>
        </div>
      </div>

      <button
        onClick={() => handleSSOLogin('saml')}
        disabled={isLoading}
        className="w-full flex items-center justify-center px-4 py-3 border border-gray-600 rounded-md shadow-sm bg-gray-700 hover:bg-gray-600 text-white font-medium disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Enterprise SSO (SAML)
      </button>

      <p className="text-center text-gray-500 text-xs mt-4">
        SSO providers must be configured by your administrator
      </p>
    </div>
  )
}
