import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import { authApi } from '../services/api'
import toast from 'react-hot-toast'

export function useAuth() {
  const navigate = useNavigate()
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    loginWithSSH,
    logout,
    fetchUser,
    clearError,
  } = useAuthStore()

  const handleLogin = useCallback(
    async (username: string, password: string) => {
      try {
        await login(username, password)
        toast.success('Logged in successfully')
        navigate('/')
      } catch {
        toast.error('Login failed')
      }
    },
    [login, navigate]
  )

  const handleSSHLogin = useCallback(
    async (username: string) => {
      try {
        // Get challenge
        const challengeResponse = await authApi.sshChallenge(username)
        const { challenge } = challengeResponse.data

        // In a real app, this would be signed by the user's SSH key
        // For now, we'll prompt them to sign it externally
        const signature = prompt(
          `Sign this challenge with your SSH key:\n${challenge}\n\nPaste the base64 signature:`
        )

        if (!signature) {
          toast.error('SSH authentication cancelled')
          return
        }

        await loginWithSSH(username, challenge, signature)
        toast.success('Logged in with SSH')
        navigate('/')
      } catch {
        toast.error('SSH authentication failed')
      }
    },
    [loginWithSSH, navigate]
  )

  const handleLogout = useCallback(() => {
    logout()
    toast.success('Logged out')
    navigate('/login')
  }, [logout, navigate])

  const switchAuthMethod = useCallback(
    async (method: 'password' | 'ssh_key') => {
      try {
        await authApi.switchAuthMethod(method)
        await fetchUser()
        toast.success(`Switched to ${method === 'password' ? 'password' : 'SSH key'} authentication`)
      } catch {
        toast.error('Failed to switch authentication method')
      }
    },
    [fetchUser]
  )

  const updateSSHKey = useCallback(
    async (sshPublicKey: string) => {
      try {
        await authApi.updateMe({ ssh_public_key: sshPublicKey })
        await fetchUser()
        toast.success('SSH key updated')
      } catch {
        toast.error('Failed to update SSH key')
      }
    },
    [fetchUser]
  )

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    handleLogin,
    handleSSHLogin,
    handleLogout,
    switchAuthMethod,
    updateSSHKey,
    clearError,
  }
}
