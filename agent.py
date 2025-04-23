import os
import re
import json
import logging
import requests
from typing import Dict, List, Any, Optional, Union

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from retriever import hybrid_search, search_all_collections
from classifier import get_classifier

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Constants
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))
MCP_SERVER_URL = f"http://localhost:{MCP_SERVER_PORT}"
MAX_CONTEXT_LENGTH = 1024  # Adjust based on model requirements

# Initialize models
embedder = SentenceTransformer('all-MiniLM-L6-v2')
classifier = get_classifier()

# Initialize LLM
model_name = "google/flan-t5-base"  # Can be changed to larger model if needed
tokenizer = None
model = None

def load_llm():
    """Load the LLM model and tokenizer."""
    global tokenizer, model
    
    if tokenizer is None or model is None:
        logger.info(f"Loading LLM model: {model_name}")
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
            logger.info("LLM model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading LLM model: {e}")
            raise

def extract_entities(text: str) -> List[str]:
    """
    Extract potential entities (teams, players) from text.
    This is a simple implementation - could be enhanced with NER models.
    
    Args:
        text: The text to extract entities from
        
    Returns:
        List of potential entity names
    """
    # Simple regex-based extraction
    # Look for capitalized words that might be names
    potential_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
    
    # Filter out common words that start with capital letters
    common_words = {"The", "A", "An", "In", "On", "At", "From", "To", "With", "By", "About"}
    filtered_entities = [entity for entity in potential_entities if entity not in common_words]
    
    return filtered_entities

def needs_mcp_integration(query: str) -> bool:
    """
    Determine if the query likely needs MCP integration.
    
    Args:
        query: The user query
        
    Returns:
        True if MCP integration is likely needed, False otherwise
    """
    # Keywords that suggest sports information is needed
    sports_keywords = [
        "score", "game", "match", "team", "player", "sport", "league", "championship",
        "tournament", "win", "lose", "play", "coach", "stadium", "last night",
        "yesterday", "upcoming", "schedule", "roster", "lineup", "stats", "statistics"
    ]
    
    # Check if any of the keywords are in the query
    query_lower = query.lower()
    for keyword in sports_keywords:
        if keyword in query_lower:
            return True
    
    return False

def call_mcp_sports_search(entity: str) -> Dict[str, Any]:
    """
    Call the MCP sports search endpoint.
    
    Args:
        entity: The entity to search for
        
    Returns:
        Search results from the MCP server
    """
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp/sports-search",
            json={"query": entity}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"MCP sports search failed: {response.status_code} - {response.text}")
            return {"results": [], "query": entity, "source": "TheSportsDB"}
    
    except Exception as e:
        logger.error(f"Error calling MCP sports search: {e}")
        return {"results": [], "query": entity, "source": "TheSportsDB"}

def call_mcp_latest_events(team_id: Optional[str] = None, team_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Call the MCP latest events endpoint.
    
    Args:
        team_id: The team ID
        team_name: The team name
        
    Returns:
        Latest events from the MCP server
    """
    if not team_id and not team_name:
        logger.error("Either team_id or team_name must be provided")
        return {"events": [], "team_info": {}, "source": "TheSportsDB"}
    
    try:
        response = requests.post(
            f"{MCP_SERVER_URL}/mcp/latest-events",
            json={"team_id": team_id, "team_name": team_name}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"MCP latest events failed: {response.status_code} - {response.text}")
            return {"events": [], "team_info": {}, "source": "TheSportsDB"}
    
    except Exception as e:
        logger.error(f"Error calling MCP latest events: {e}")
        return {"events": [], "team_info": {}, "source": "TheSportsDB"}

def build_llm_prompt(
    user_query: str,
    rag_snippets: List[Dict[str, Any]],
    tags: Dict[str, List[str]],
    mcp_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build a prompt for the LLM.
    
    Args:
        user_query: The user's query
        rag_snippets: The RAG snippets
        tags: Classification tags for the snippets
        mcp_data: Optional MCP data
        
    Returns:
        The formatted prompt
    """
    prompt = f"User Query: {user_query}\n\n"
    
    # Add RAG snippets
    if rag_snippets:
        prompt += "Context from Documents:\n"
        for i, snippet in enumerate(rag_snippets):
            snippet_id = snippet.get("id", f"snippet_{i}")
            content = snippet.get("content", "")
            metadata = snippet.get("metadata", {})
            
            source = metadata.get("source", "Unknown")
            category = metadata.get("category", "Unknown")
            
            # Get tags for this snippet
            snippet_tags = tags.get(snippet_id, [])
            tags_str = ", ".join(snippet_tags) if snippet_tags else "Unclassified"
            
            prompt += f"[Snippet {i+1} (Source: {source}, Category: {category}, Tags: {tags_str})]\n"
            
            # Truncate content if it's too long
            max_snippet_length = 200  # Adjust as needed
            if len(content) > max_snippet_length:
                content = content[:max_snippet_length] + "..."
            
            prompt += f"{content}\n\n"
    
    # Add MCP data if available
    if mcp_data:
        prompt += "Live Sports Data:\n"
        
        # Format MCP data based on what's available
        if "results" in mcp_data:
            # Search results
            prompt += f"Search results for '{mcp_data.get('query', '')}':\n"
            for i, result in enumerate(mcp_data.get("results", [])[:3]):  # Limit to top 3
                result_type = result.get("type", "Unknown")
                name = result.get("name", "Unknown")
                
                if result_type == "team":
                    sport = result.get("sport", "Unknown")
                    league = result.get("league", "Unknown")
                    prompt += f"- Team: {name} (Sport: {sport}, League: {league})\n"
                elif result_type == "player":
                    team = result.get("team", "Unknown")
                    position = result.get("position", "Unknown")
                    prompt += f"- Player: {name} (Team: {team}, Position: {position})\n"
        
        if "events" in mcp_data:
            # Events data
            team_info = mcp_data.get("team_info", {})
            team_name = team_info.get("name", "Unknown")
            
            prompt += f"Events for {team_name}:\n"
            
            # Group events by status
            completed_events = []
            upcoming_events = []
            
            for event in mcp_data.get("events", []):
                if event.get("status") == "completed":
                    completed_events.append(event)
                else:
                    upcoming_events.append(event)
            
            # Add completed events
            if completed_events:
                prompt += "Recent results:\n"
                for event in completed_events[:3]:  # Limit to top 3
                    name = event.get("name", "Unknown")
                    date = event.get("date", "Unknown")
                    home_score = event.get("home_score", "?")
                    away_score = event.get("away_score", "?")
                    prompt += f"- {name} ({date}): {home_score}-{away_score}\n"
            
            # Add upcoming events
            if upcoming_events:
                prompt += "Upcoming matches:\n"
                for event in upcoming_events[:3]:  # Limit to top 3
                    name = event.get("name", "Unknown")
                    date = event.get("date", "Unknown")
                    venue = event.get("venue", "Unknown")
                    prompt += f"- {name} ({date} at {venue})\n"
        
        prompt += "\n"
    
    # Add instruction for the LLM
    prompt += "Based on the user query and the provided context and live data, answer the user's query.\n\n"
    prompt += "Answer:"
    
    return prompt

def run_query(user_query: str) -> Dict[str, Any]:
    """
    Main function to process a user query.
    
    Args:
        user_query: The user's query
        
    Returns:
        Dictionary containing the results
    """
    logger.info(f"Processing query: {user_query}")
    
    # Ensure LLM is loaded
    load_llm()
    
    # Step 1: Embed the query
    query_embedding = embedder.encode(user_query).tolist()
    
    # Step 2: Determine if MCP integration is needed
    needs_mcp = needs_mcp_integration(user_query)
    
    # Step 3: Retrieve relevant documents using RAG
    rag_snippets = hybrid_search(user_query, k=5)
    
    # Step 4: Classify the retrieved snippets
    tags = {}
    for snippet in rag_snippets:
        snippet_id = snippet.get("id")
        content = snippet.get("content", "")
        
        # Get classification tags
        classification_result = classifier.get_all_labels_above_threshold(content, threshold=0.3)
        tags[snippet_id] = classification_result
    
    # Step 5: Call MCP if needed
    mcp_data = None
    if needs_mcp:
        # Extract potential entities
        entities = extract_entities(user_query)
        
        if entities:
            # Use the first entity for simplicity
            # In a more sophisticated system, we might try multiple entities
            # or use entity disambiguation
            entity = entities[0]
            
            # Search for the entity
            search_results = call_mcp_sports_search(entity)
            
            if search_results.get("results"):
                mcp_data = search_results
                
                # If we found a team, get its events
                for result in search_results.get("results", []):
                    if result.get("type") == "team":
                        team_id = result.get("id")
                        if team_id:
                            events_data = call_mcp_latest_events(team_id=team_id)
                            if events_data.get("events"):
                                mcp_data = events_data
                                break
    
    # Step 6: Build the LLM prompt
    prompt = build_llm_prompt(user_query, rag_snippets, tags, mcp_data)
    
    # Step 7: Generate the answer using the LLM
    inputs = tokenizer(prompt, return_tensors="pt", max_length=MAX_CONTEXT_LENGTH, truncation=True)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            num_beams=4,
            temperature=0.7,
            top_p=0.9,
            do_sample=True
        )
    
    final_answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Step 8: Return the results
    return {
        "query": user_query,
        "rag_snippets": rag_snippets,
        "tags": tags,
        "mcp_data": mcp_data,
        "final_answer": final_answer
    }

if __name__ == "__main__":
    # Simple test
    test_query = "What happened in the Lakers game last night?"
    print(f"Testing agent with query: '{test_query}'")
    
    result = run_query(test_query)
    
    print("\nFinal Answer:")
    print(result["final_answer"])
    
    print("\nRAG Snippets:")
    for i, snippet in enumerate(result["rag_snippets"]):
        print(f"Snippet {i+1}: {snippet['content'][:50]}...")
    
    print("\nTags:")
    for snippet_id, snippet_tags in result["tags"].items():
        print(f"Snippet {snippet_id}: {snippet_tags}")
    
    if result["mcp_data"]:
        print("\nMCP Data:")
        print(json.dumps(result["mcp_data"], indent=2))
