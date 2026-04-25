import { useQuery } from '@tanstack/react-query'
import { agentApi } from '../services/api'
import { useSettingsStore } from '../stores/settingsStore'

export function useLLMProviders() {
  return useQuery({
    queryKey: ['llm-providers'],
    queryFn: async () => {
      const response = await agentApi.getProviders()
      return response.data.providers as string[]
    },
    staleTime: 1000 * 60 * 30, // 30 minutes
  })
}

export function useDefaultLLMProvider() {
  const { defaultLLMProvider, setDefaultLLMProvider } = useSettingsStore()
  const { data: providers } = useLLMProviders()

  // Ensure default provider is valid
  const validProvider =
    providers?.includes(defaultLLMProvider)
      ? defaultLLMProvider
      : providers?.[0] ?? 'openai'

  return {
    provider: validProvider,
    setProvider: setDefaultLLMProvider,
    availableProviders: providers ?? [],
  }
}
