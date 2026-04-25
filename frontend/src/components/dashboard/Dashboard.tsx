import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, RefreshCw } from 'lucide-react'
import { repoApi } from '../../services/api'
import toast from 'react-hot-toast'
import RepositoryList from './RepositoryList'
import AddRepositoryModal from './AddRepositoryModal'

export default function Dashboard() {
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const queryClient = useQueryClient()

  const { data: repositories, isLoading, refetch } = useQuery({
    queryKey: ['repositories'],
    queryFn: async () => {
      const response = await repoApi.list()
      return response.data
    },
  })

  const createMutation = useMutation({
    mutationFn: async (data: {
      name: string
      url: string
      description?: string
      branch?: string
      current_jdk_version?: string
      target_jdk_version?: string
    }) => {
      const response = await repoApi.create(data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['repositories'] })
      setIsAddModalOpen(false)
      toast.success('Repository added')
    },
    onError: () => {
      toast.error('Failed to add repository')
    },
  })

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Repositories</h1>
          <p className="text-gray-400 mt-1">
            Manage your Java repositories and analyze JDK upgrade impacts
          </p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => refetch()}
            className="btn btn-secondary flex items-center"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="btn btn-primary flex items-center"
          >
            <Plus className="h-4 w-4 mr-2" />
            Add Repository
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      ) : repositories?.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-400">No repositories yet</p>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="mt-4 btn btn-primary"
          >
            Add your first repository
          </button>
        </div>
      ) : (
        <RepositoryList repositories={repositories || []} />
      )}

      <AddRepositoryModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onSubmit={(data) => createMutation.mutate(data)}
        isLoading={createMutation.isPending}
      />
    </div>
  )
}
