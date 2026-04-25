import { useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'
import toast from 'react-hot-toast'

export function useAuth() {
  const navigate = useNavigate()
  const {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
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

  const handleLogout = useCallback(() => {
    logout()
    toast.success('Logged out')
    navigate('/login')
  }, [logout, navigate])

  const refreshUser = useCallback(async () => {
    try {
      await fetchUser()
    } catch {
      // User not authenticated
    }
  }, [fetchUser])

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    handleLogin,
    handleLogout,
    refreshUser,
    clearError,
  }
}
