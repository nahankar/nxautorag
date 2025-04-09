import { useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom'
import DataSourceConfig from './components/DataSourceConfig.jsx'
import QueryInterface from './components/QueryInterface.jsx'
import './App.css'

function App() {
  const [answer, setAnswer] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <header className="bg-white shadow-sm">
          <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
            <h1 className="text-3xl font-bold text-gray-900">AutoRAG Tool</h1>
            
            <nav className="mt-4">
              <ul className="flex justify-center">
                <li className="w-32 text-center">
                  <Link
                    to="/config"
                    className="text-gray-600 hover:text-blue-600 font-medium"
                  >
                    Configure
                  </Link>
                </li>
                <li className="w-32 text-center">
                  <Link
                    to="/query"
                    className="text-gray-600 hover:text-blue-600 font-medium"
                  >
                    Query
                  </Link>
                </li>
              </ul>
            </nav>
          </div>
        </header>
        
        <main className="py-6">
          <Routes>
            <Route path="/" element={<DataSourceConfig />} />
            <Route path="/config" element={<DataSourceConfig />} />
            <Route 
              path="/query" 
              element={
                <QueryInterface 
                  setAnswer={setAnswer}
                  setIsLoading={setIsLoading}
                  setError={setError}
                />
              } 
            />
          </Routes>
        </main>
        
        <footer className="bg-white border-t border-gray-200 py-6">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <p className="text-center text-gray-500 text-sm">
              AutoRAG Tool &copy; {new Date().getFullYear()}
            </p>
          </div>
        </footer>
      </div>
    </Router>
  )
}

export default App
