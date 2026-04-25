import { Outlet, Link, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  GitBranch,
  MessageSquare,
  History,
  FileText,
  Settings,
  LogOut,
} from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import clsx from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Chat Agent', href: '/chat', icon: MessageSquare },
  { name: 'Audit Log', href: '/audit', icon: FileText },
  { name: 'History', href: '/history', icon: History },
  { name: 'Settings', href: '/settings', icon: Settings },
]

export default function Layout() {
  const location = useLocation()
  const { user, handleLogout } = useAuth()

  return (
    <div className="flex h-screen bg-gray-900">
      {/* Sidebar */}
      <div className="hidden md:flex md:w-64 md:flex-col">
        <div className="flex flex-col flex-grow pt-5 overflow-y-auto bg-gray-800 border-r border-gray-700">
          <div className="flex items-center flex-shrink-0 px-4">
            <GitBranch className="h-8 w-8 text-blue-500" />
            <span className="ml-2 text-xl font-bold text-white">JavaPatching</span>
          </div>

          <div className="mt-8 flex-grow flex flex-col">
            <nav className="flex-1 px-2 space-y-1">
              {navigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={clsx(
                      'group flex items-center px-2 py-2 text-sm font-medium rounded-md',
                      isActive
                        ? 'bg-gray-900 text-white'
                        : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                    )}
                  >
                    <item.icon
                      className={clsx(
                        'mr-3 flex-shrink-0 h-5 w-5',
                        isActive ? 'text-blue-500' : 'text-gray-400 group-hover:text-gray-300'
                      )}
                    />
                    {item.name}
                  </Link>
                )
              })}
            </nav>
          </div>

          <div className="flex-shrink-0 flex border-t border-gray-700 p-4">
            <div className="flex items-center w-full">
              <div className="flex-1">
                <p className="text-sm font-medium text-white">{user?.username}</p>
                <p className="text-xs text-gray-400">{user?.email || 'No email'}</p>
              </div>
              <button
                onClick={handleLogout}
                className="ml-3 p-2 text-gray-400 hover:text-white rounded-md hover:bg-gray-700"
              >
                <LogOut className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <main className="flex-1 relative overflow-y-auto focus:outline-none">
          <div className="py-6">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8">
              <Outlet />
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
