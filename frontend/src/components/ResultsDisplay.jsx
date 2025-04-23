function ResultsDisplay({ results }) {
  const { query, final_answer, rag_snippets, tags, mcp_data } = results

  return (
    <div className="results-container">
      <div className="answer-card">
        <h2>Answer</h2>
        <p>{final_answer}</p>
      </div>

      {rag_snippets && rag_snippets.length > 0 && (
        <div className="snippets-container">
          <h3>Source Information</h3>
          {rag_snippets.map((snippet, index) => (
            <div key={index} className="snippet-card">
              <div className="snippet-metadata">
                <strong>Source:</strong> {snippet.metadata?.source || 'Unknown'} | 
                <strong> Category:</strong> {snippet.metadata?.category || 'Unknown'}
              </div>
              <p>{snippet.content}</p>
              
              {tags && tags[snippet.id] && (
                <div className="tags-container">
                  {tags[snippet.id].map((tag, tagIndex) => (
                    <span key={tagIndex} className="tag">{tag}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {mcp_data && (
        <div className="card">
          <h3>Live Sports Data</h3>
          
          {mcp_data.results && (
            <div>
              <h4>Search Results for "{mcp_data.query}"</h4>
              <ul>
                {mcp_data.results.map((result, index) => (
                  <li key={index}>
                    {result.type === 'team' ? (
                      <span>
                        <strong>{result.name}</strong> ({result.sport}, {result.league})
                      </span>
                    ) : (
                      <span>
                        <strong>{result.name}</strong> ({result.team}, {result.position})
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {mcp_data.events && (
            <div>
              <h4>Events for {mcp_data.team_info?.name}</h4>
              
              {/* Group events by status */}
              {mcp_data.events.filter(e => e.status === 'completed').length > 0 && (
                <div>
                  <h5>Recent Results</h5>
                  <ul>
                    {mcp_data.events
                      .filter(e => e.status === 'completed')
                      .map((event, index) => (
                        <li key={index}>
                          {event.name} ({event.date}): {event.home_score}-{event.away_score}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
              
              {mcp_data.events.filter(e => e.status === 'upcoming').length > 0 && (
                <div>
                  <h5>Upcoming Matches</h5>
                  <ul>
                    {mcp_data.events
                      .filter(e => e.status === 'upcoming')
                      .map((event, index) => (
                        <li key={index}>
                          {event.name} ({event.date} at {event.venue})
                        </li>
                      ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ResultsDisplay
