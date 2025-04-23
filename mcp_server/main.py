import os
import logging
from typing import Dict, Any, List, Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
SPORTS_DB_API_KEY = os.getenv("SPORTS_DB_API_KEY", "YOUR_API_KEY_HERE")
SPORTS_DB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))

# Initialize FastAPI app
app = FastAPI(
    title="Model Context Protocol Server",
    description="MCP Server for sports data integration",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Pydantic models for request/response
class SearchQuery(BaseModel):
    query: str

class TeamEventsQuery(BaseModel):
    team_id: Optional[str] = None
    team_name: Optional[str] = None

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    query: str
    source: str = "TheSportsDB"

class EventsResponse(BaseModel):
    events: List[Dict[str, Any]]
    team_info: Dict[str, Any]
    source: str = "TheSportsDB"

@app.get("/")
async def root():
    """Root endpoint to check if the server is running."""
    return {"status": "ok", "message": "MCP Server is running"}

@app.post("/mcp/sports-search", response_model=SearchResponse)
async def sports_search(search_query: SearchQuery):
    """
    Search for teams, players, or events in TheSportsDB.
    
    Args:
        search_query: The search query
        
    Returns:
        Search results from TheSportsDB
    """
    query = search_query.query
    logger.info(f"Sports search request: {query}")
    
    try:
        # Search for teams
        teams_url = f"{SPORTS_DB_BASE_URL}/{SPORTS_DB_API_KEY}/searchteams.php"
        teams_response = requests.get(teams_url, params={"t": query})
        teams_data = teams_response.json()
        
        # Search for players
        players_url = f"{SPORTS_DB_BASE_URL}/{SPORTS_DB_API_KEY}/searchplayers.php"
        players_response = requests.get(players_url, params={"p": query})
        players_data = players_response.json()
        
        # Combine results
        results = []
        
        if teams_data.get("teams"):
            for team in teams_data["teams"]:
                results.append({
                    "type": "team",
                    "id": team.get("idTeam"),
                    "name": team.get("strTeam"),
                    "sport": team.get("strSport"),
                    "league": team.get("strLeague"),
                    "country": team.get("strCountry"),
                    "description": team.get("strDescriptionEN"),
                    "logo": team.get("strTeamBadge"),
                    "website": team.get("strWebsite")
                })
        
        if players_data.get("player"):
            for player in players_data["player"]:
                results.append({
                    "type": "player",
                    "id": player.get("idPlayer"),
                    "name": player.get("strPlayer"),
                    "team": player.get("strTeam"),
                    "sport": player.get("strSport"),
                    "nationality": player.get("strNationality"),
                    "position": player.get("strPosition"),
                    "description": player.get("strDescriptionEN"),
                    "thumb": player.get("strThumb")
                })
        
        logger.info(f"Sports search returned {len(results)} results")
        return SearchResponse(results=results, query=query)
    
    except Exception as e:
        logger.error(f"Error in sports search: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching sports data: {str(e)}")

@app.post("/mcp/latest-events", response_model=EventsResponse)
async def latest_events(query: TeamEventsQuery):
    """
    Get latest events for a team.
    
    Args:
        query: The team query (either team_id or team_name must be provided)
        
    Returns:
        Latest events for the team
    """
    if not query.team_id and not query.team_name:
        raise HTTPException(status_code=400, detail="Either team_id or team_name must be provided")
    
    team_id = query.team_id
    team_name = query.team_name
    
    logger.info(f"Latest events request for team_id={team_id}, team_name={team_name}")
    
    try:
        # If only team name is provided, search for the team first
        if not team_id and team_name:
            teams_url = f"{SPORTS_DB_BASE_URL}/{SPORTS_DB_API_KEY}/searchteams.php"
            teams_response = requests.get(teams_url, params={"t": team_name})
            teams_data = teams_response.json()
            
            if not teams_data.get("teams"):
                raise HTTPException(status_code=404, detail=f"Team not found: {team_name}")
            
            team_id = teams_data["teams"][0]["idTeam"]
            team_info = {
                "id": team_id,
                "name": teams_data["teams"][0].get("strTeam"),
                "sport": teams_data["teams"][0].get("strSport"),
                "league": teams_data["teams"][0].get("strLeague"),
                "country": teams_data["teams"][0].get("strCountry")
            }
        else:
            # Get team info
            team_url = f"{SPORTS_DB_BASE_URL}/{SPORTS_DB_API_KEY}/lookupteam.php"
            team_response = requests.get(team_url, params={"id": team_id})
            team_data = team_response.json()
            
            if not team_data.get("teams"):
                raise HTTPException(status_code=404, detail=f"Team not found with ID: {team_id}")
            
            team_info = {
                "id": team_id,
                "name": team_data["teams"][0].get("strTeam"),
                "sport": team_data["teams"][0].get("strSport"),
                "league": team_data["teams"][0].get("strLeague"),
                "country": team_data["teams"][0].get("strCountry")
            }
        
        # Get last 5 events
        events_url = f"{SPORTS_DB_BASE_URL}/{SPORTS_DB_API_KEY}/eventslast.php"
        events_response = requests.get(events_url, params={"id": team_id})
        events_data = events_response.json()
        
        # Get next 5 events
        next_events_url = f"{SPORTS_DB_BASE_URL}/{SPORTS_DB_API_KEY}/eventsnext.php"
        next_events_response = requests.get(next_events_url, params={"id": team_id})
        next_events_data = next_events_response.json()
        
        # Process events
        events = []
        
        if events_data.get("results"):
            for event in events_data["results"]:
                events.append({
                    "id": event.get("idEvent"),
                    "name": event.get("strEvent"),
                    "date": event.get("dateEvent"),
                    "time": event.get("strTime"),
                    "status": "completed",
                    "home_team": event.get("strHomeTeam"),
                    "away_team": event.get("strAwayTeam"),
                    "home_score": event.get("intHomeScore"),
                    "away_score": event.get("intAwayScore"),
                    "venue": event.get("strVenue"),
                    "league": event.get("strLeague")
                })
        
        if next_events_data.get("events"):
            for event in next_events_data["events"]:
                events.append({
                    "id": event.get("idEvent"),
                    "name": event.get("strEvent"),
                    "date": event.get("dateEvent"),
                    "time": event.get("strTime"),
                    "status": "upcoming",
                    "home_team": event.get("strHomeTeam"),
                    "away_team": event.get("strAwayTeam"),
                    "venue": event.get("strVenue"),
                    "league": event.get("strLeague")
                })
        
        # Sort events by date
        events.sort(key=lambda x: x["date"], reverse=True)
        
        logger.info(f"Latest events returned {len(events)} events for team {team_info['name']}")
        return EventsResponse(events=events, team_info=team_info)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in latest events: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching events: {str(e)}")

@app.get("/mcp/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting MCP Server on port {MCP_SERVER_PORT}")
    uvicorn.run("main:app", host="0.0.0.0", port=MCP_SERVER_PORT, reload=True)
