import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SettingsState {
  defaultLLMProvider: string
  theme: 'light' | 'dark'
  autoRefresh: boolean
  refreshInterval: number

  setDefaultLLMProvider: (provider: string) => void
  setTheme: (theme: 'light' | 'dark') => void
  setAutoRefresh: (enabled: boolean) => void
  setRefreshInterval: (interval: number) => void
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      defaultLLMProvider: 'openai',
      theme: 'dark',
      autoRefresh: true,
      refreshInterval: 30000, // 30 seconds

      setDefaultLLMProvider: (provider: string) => set({ defaultLLMProvider: provider }),
      setTheme: (theme: 'light' | 'dark') => set({ theme }),
      setAutoRefresh: (enabled: boolean) => set({ autoRefresh: enabled }),
      setRefreshInterval: (interval: number) => set({ refreshInterval: interval }),
    }),
    {
      name: 'settings-storage',
    }
  )
)
