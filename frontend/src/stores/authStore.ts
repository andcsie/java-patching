import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '../services/api'

interface User {
  id: string
  username: string
  email?: string
  is_active: boolean
  is_superuser: boolean
  auth_method?: string
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  login: (username: string, password: string) => Promise<void>
  loginWithSSO: (provider: string, code: string) => Promise<void>
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

      loginWithSSO: async (provider: string, code: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.ssoCallback(provider, code)
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
          const message = error instanceof Error ? error.message : 'SSO authentication failed'
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
        const token = localStorage.getItem('access_token')
        if (!token) {
          get().logout()
          return
        }
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
      onRehydrateStorage: () => (state) => {
        // Sync persisted state with actual localStorage tokens
        if (state) {
          const token = localStorage.getItem('access_token')
          if (!token && state.isAuthenticated) {
            // Token was cleared but state says authenticated - fix it
            state.logout()
          }
        }
      },
    }
  )
)
