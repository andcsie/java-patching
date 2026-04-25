import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import LoginPage from './components/auth/LoginPage'
import Dashboard from './components/dashboard/Dashboard'
import RepositoryDetail from './components/dashboard/RepositoryDetail'
import AnalysisView from './components/analysis/AnalysisView'
import ChatInterface from './components/agent/ChatInterface'
import AuditLog from './components/audit/AuditLog'
import HistoryViewer from './components/audit/HistoryViewer'
import Settings from './components/Settings'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const token = localStorage.getItem('access_token')

  // Must have both auth state and actual token
  if (!isAuthenticated || !token) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route
        path="/"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="repositories/:id" element={<RepositoryDetail />} />
        <Route path="analyses/:id" element={<AnalysisView />} />
        <Route path="chat" element={<ChatInterface />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="history" element={<HistoryViewer />} />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App
