import { useState } from 'react'
import SearchBar from './components/SearchBar'
import ResultsDisplay from './components/ResultsDisplay'
import axios from 'axios'

function App() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleSearch = async (searchQuery) => {
    setQuery(searchQuery)
    setLoading(true)
    setError(null)
    
    try {
      const response = await axios.post('http://localhost:8002/query', {
        query: searchQuery
      })
      
      setResults(response.data)
    } catch (err) {
      console.error('Error fetching results:', err)
      setError('An error occurred while processing your query. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1>Context-Aware Assistant</h1>
      <SearchBar onSearch={handleSearch} />
      
      {loading && (
        <div className="loading">
          <div className="loading-spinner"></div>
        </div>
      )}
      
      {error && (
        <div className="card">
          <p style={{ color: 'red' }}>{error}</p>
        </div>
      )}
      
      {results && !loading && (
        <ResultsDisplay results={results} />
      )}
    </div>
  )
}

export default App
