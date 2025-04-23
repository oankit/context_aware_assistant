import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
OUTPUT_DIR = Path("../data/industry_news")
MAX_RESULTS = 1000  # Number of stories to download
DAYS_BACK = 30  # Get stories from the last 30 days

def setup_output_directory():
    """Create the output directory if it doesn't exist."""
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created output directory: {OUTPUT_DIR}")
    else:
        logger.info(f"Output directory already exists: {OUTPUT_DIR}")

def get_bigquery_client():
    """
    Get a BigQuery client.
    
    If you have a service account key, set GOOGLE_APPLICATION_CREDENTIALS env var.
    Otherwise, use Application Default Credentials.
    """
    try:
        # Check if service account key file is specified
        key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        
        if key_path and os.path.exists(key_path):
            # Use service account key file
            credentials = service_account.Credentials.from_service_account_file(
                key_path, 
                scopes=["https://www.googleapis.com/auth/bigquery"]
            )
            client = bigquery.Client(credentials=credentials, project=credentials.project_id)
            logger.info(f"Created BigQuery client using service account key: {key_path}")
        else:
            # Use Application Default Credentials
            client = bigquery.Client()
            logger.info("Created BigQuery client using Application Default Credentials")
        
        return client
    
    except Exception as e:
        logger.error(f"Error creating BigQuery client: {e}")
        raise

def query_hacker_news(client, max_results=MAX_RESULTS, days_back=DAYS_BACK):
    """
    Query the Hacker News dataset for recent stories.
    
    Args:
        client: BigQuery client
        max_results: Maximum number of results to return
        days_back: Number of days back to query
        
    Returns:
        List of story dictionaries
    """
    # Calculate the date threshold
    threshold_date = datetime.now() - timedelta(days=days_back)
    threshold_timestamp = int(threshold_date.timestamp())
    
    # Construct the query
    query = f"""
    SELECT
      id,
      title,
      url,
      text,
      time_ts,
      score,
      TIMESTAMP_SECONDS(time_ts) as datetime,
      `by` as author,
      descendants as comment_count
    FROM
      `bigquery-public-data.hacker_news.stories`
    WHERE
      time_ts >= {threshold_timestamp}
      AND score > 10
      AND title IS NOT NULL
      AND deleted IS NULL
    ORDER BY
      score DESC
    LIMIT
      {max_results}
    """
    
    try:
        logger.info(f"Querying Hacker News stories from the last {days_back} days")
        query_job = client.query(query)
        results = query_job.result()
        
        # Convert to list of dictionaries
        stories = []
        for row in results:
            story = dict(row.items())
            # Convert datetime to string
            if "datetime" in story:
                story["datetime"] = story["datetime"].isoformat()
            stories.append(story)
        
        logger.info(f"Retrieved {len(stories)} Hacker News stories")
        return stories
    
    except Exception as e:
        logger.error(f"Error querying Hacker News dataset: {e}")
        return []

def save_stories(stories):
    """
    Save the stories to files.
    
    Args:
        stories: List of story dictionaries
        
    Returns:
        Number of stories saved
    """
    count = 0
    
    for story in stories:
        try:
            # Create a filename from the ID and title
            story_id = story.get("id")
            title = story.get("title", "Untitled")
            
            # Clean the title for use in filename
            clean_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
            clean_title = clean_title.strip().replace(" ", "_")[:50]
            
            filename = f"hn_{story_id}_{clean_title}.json"
            file_path = OUTPUT_DIR / filename
            
            # Add source information
            story["source"] = "Hacker News"
            story["source_id"] = f"hn_{story_id}"
            
            # Write the story to a JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(story, f, indent=2)
            
            logger.info(f"Saved story to {file_path}")
            count += 1
        
        except Exception as e:
            logger.error(f"Error saving story {story.get('id')}: {e}")
    
    return count

def download_hacker_news():
    """Main function to download Hacker News stories."""
    setup_output_directory()
    
    try:
        # Get BigQuery client
        client = get_bigquery_client()
        
        # Query Hacker News dataset
        stories = query_hacker_news(client)
        
        if not stories:
            logger.warning("No stories retrieved from Hacker News dataset")
            return
        
        # Save stories to files
        saved_count = save_stories(stories)
        
        logger.info(f"Download complete. Saved {saved_count} Hacker News stories.")
    
    except Exception as e:
        logger.error(f"Error downloading Hacker News stories: {e}")

if __name__ == "__main__":
    logger.info("Starting Hacker News download")
    download_hacker_news()
    logger.info("Hacker News download complete")
