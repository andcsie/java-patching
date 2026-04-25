import { useState } from 'react'
import { X } from 'lucide-react'

interface Props {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: {
    name: string
    url: string
    description?: string
    branch?: string
    current_jdk_version?: string
    target_jdk_version?: string
  }) => void
  isLoading: boolean
}

export default function AddRepositoryModal({ isOpen, onClose, onSubmit, isLoading }: Props) {
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    description: '',
    branch: 'main',
    current_jdk_version: '',
    target_jdk_version: '',
  })

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      name: formData.name,
      url: formData.url,
      description: formData.description || undefined,
      branch: formData.branch || undefined,
      current_jdk_version: formData.current_jdk_version || undefined,
      target_jdk_version: formData.target_jdk_version || undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-black/50" onClick={onClose}></div>

        <div className="relative bg-gray-800 rounded-lg max-w-md w-full p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-white">Add Repository</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-white">
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Name *
              </label>
              <input
                type="text"
                required
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="input"
                placeholder="my-java-project"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Repository URL or Path *
              </label>
              <input
                type="text"
                required
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                className="input"
                placeholder="https://github.com/user/repo.git"
              />
              <p className="text-xs text-gray-500 mt-1">
                Git URL, or local path: /path/to/repo
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="input"
                rows={2}
                placeholder="Optional description"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1">
                Branch
              </label>
              <input
                type="text"
                value={formData.branch}
                onChange={(e) => setFormData({ ...formData, branch: e.target.value })}
                className="input"
                placeholder="main"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Current JDK
                </label>
                <input
                  type="text"
                  value={formData.current_jdk_version}
                  onChange={(e) =>
                    setFormData({ ...formData, current_jdk_version: e.target.value })
                  }
                  className="input"
                  placeholder="11.0.18"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-1">
                  Target JDK
                </label>
                <input
                  type="text"
                  value={formData.target_jdk_version}
                  onChange={(e) =>
                    setFormData({ ...formData, target_jdk_version: e.target.value })
                  }
                  className="input"
                  placeholder="11.0.22"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-4">
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" disabled={isLoading} className="btn btn-primary">
                {isLoading ? 'Adding...' : 'Add Repository'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
