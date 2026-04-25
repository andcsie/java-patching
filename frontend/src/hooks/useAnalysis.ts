import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { impactApi } from '../services/api'
import toast from 'react-hot-toast'

export function useAnalyses(repositoryId?: string) {
  return useQuery({
    queryKey: ['analyses', repositoryId],
    queryFn: async () => {
      const response = await impactApi.listAnalyses(repositoryId)
      return response.data
    },
  })
}

export function useAnalysis(id: string) {
  return useQuery({
    queryKey: ['analysis', id],
    queryFn: async () => {
      const response = await impactApi.getAnalysis(id)
      return response.data
    },
    refetchInterval: (query) => {
      // Auto-refresh while analysis is running
      const data = query.state.data
      if (data?.status === 'pending' || data?.status === 'running') {
        return 5000 // Refresh every 5 seconds
      }
      return false
    },
  })
}

export function useStartAnalysis() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (data: {
      repository_id: string
      from_version: string
      to_version: string
      llm_provider?: string
    }) => {
      const response = await impactApi.startAnalysis(data)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['analyses'] })
      toast.success('Analysis started')
      return data
    },
    onError: () => {
      toast.error('Failed to start analysis')
    },
  })
}

export function useDeleteAnalysis() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string) => {
      await impactApi.deleteAnalysis(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['analyses'] })
      toast.success('Analysis deleted')
    },
    onError: () => {
      toast.error('Failed to delete analysis')
    },
  })
}
