import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '../services/api'

interface User {
  id: string
  username: string
  email?: string
  is_active: boolean
  is_superuser: boolean
  preferred_auth_method: string
  has_password_auth: boolean
  has_ssh_auth: boolean
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  login: (username: string, password: string) => Promise<void>
  loginWithSSH: (username: string, challenge: string, signature: string) => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
  updateUser: (data: Partial<User>) => void
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.login(username, password)
          const { access_token, refresh_token } = response.data

          localStorage.setItem('access_token', access_token)
          localStorage.setItem('refresh_token', refresh_token)

          set({
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
          })

          // Fetch user info
          await get().fetchUser()
        } catch (error: unknown) {
          const message = error instanceof Error ? error.message : 'Login failed'
          set({ error: message, isLoading: false })
          throw error
        }
      },

      loginWithSSH: async (username: string, challenge: string, signature: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.sshVerify(username, challenge, signature)
          const { access_token, refresh_token } = response.data

          localStorage.setItem('access_token', access_token)
          localStorage.setItem('refresh_token', refresh_token)

          set({
            accessToken: access_token,
            refreshToken: refresh_token,
            isAuthenticated: true,
            isLoading: false,
          })

          await get().fetchUser()
        } catch (error: unknown) {
          const message = error instanceof Error ? error.message : 'SSH authentication failed'
          set({ error: message, isLoading: false })
          throw error
        }
      },

      logout: () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        })
      },

      fetchUser: async () => {
        try {
          const response = await authApi.getMe()
          set({ user: response.data })
        } catch {
          get().logout()
        }
      },

      updateUser: (data: Partial<User>) => {
        const currentUser = get().user
        if (currentUser) {
          set({ user: { ...currentUser, ...data } })
        }
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
        user: state.user,
      }),
    }
  )
)
