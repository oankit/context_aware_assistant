import { useState } from 'react'

function SearchBar({ onSearch }) {
  const [inputValue, setInputValue] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (inputValue.trim()) {
      onSearch(inputValue)
    }
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="text"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        placeholder="Ask me anything about media, sports, or broadcasts..."
        aria-label="Search query"
      />
      <button type="submit">Search</button>
    </form>
  )
}

export default SearchBar
