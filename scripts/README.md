# Utility Scripts

This directory contains utility scripts for the Context-Aware Assistant project.

## Hacker News Downloader

The `download_hacker_news.py` script downloads tech industry news from the Google BigQuery public dataset `bigquery-public-data.hacker_news` and saves them to the `data/industry_news` directory for use with the assistant.

### Prerequisites

Make sure you have the required dependencies installed:

```bash
pip install google-cloud-bigquery
```

This is already included in the main `requirements.txt` file.

### Authentication

To access BigQuery, you need to authenticate with Google Cloud:

1. **Option 1: Service Account Key**
   - Create a service account in the Google Cloud Console
   - Generate a JSON key file
   - Set the environment variable:
     ```bash
     # On Windows
     set GOOGLE_APPLICATION_CREDENTIALS=path\to\your\service-account-key.json
     
     # On Linux/Mac
     export GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json
     ```

2. **Option 2: Application Default Credentials**
   - Install the Google Cloud SDK
   - Run `gcloud auth application-default login`

### Usage

To run the script:

```bash
# Navigate to the scripts directory
cd context_aware_assistant/scripts

# Run the script
python download_hacker_news.py
```

### Configuration

You can modify the following constants at the top of the script:

- `OUTPUT_DIR`: The directory where stories will be saved
- `MAX_RESULTS`: Number of stories to download (default: 1000)
- `DAYS_BACK`: Number of days back to query (default: 30)

### Output

The script will:

1. Create the output directory if it doesn't exist
2. Connect to Google BigQuery
3. Query the Hacker News dataset for recent stories
4. Save each story as a JSON file with the format: `hn_[id]_[title].json`

Each JSON file contains:
- Story ID
- Title
- URL
- Text content (if available)
- Timestamp
- Score
- Author
- Comment count
- Source information

### Integration with the Assistant

After downloading the Hacker News stories, you can run the main ingestion process to index them:

```bash
# Navigate to the project root
cd ..

# Run the ingestion script
python ingest.py
```

This will process the downloaded stories, generate embeddings, and index them in both ChromaDB and Whoosh, making them available for the assistant to use when answering queries about tech industry news.

## CNN Transcript Downloader

The `download_cnn_transcripts.py` script downloads broadcast transcripts from CNN's transcript website (https://transcripts.cnn.com/) and saves them to the `data/broadcast_transcripts` directory for use with the assistant.

### Prerequisites

Make sure you have the required dependencies installed:

```bash
pip install beautifulsoup4 requests
```

These are already included in the main `requirements.txt` file.

### Usage

To run the script:

```bash
# Navigate to the scripts directory
cd context_aware_assistant/scripts

# Run the script
python download_cnn_transcripts.py
```

### Configuration

You can modify the following constants at the top of the script:

- `BASE_URL`: The base URL of the CNN transcripts website
- `OUTPUT_DIR`: The directory where transcripts will be saved
- `MAX_PAGES`: Number of pages to scrape (default: 5)
- `DELAY`: Delay between requests in seconds (default: 1)

### Output

The script will:

1. Create the output directory if it doesn't exist
2. Download transcript pages from CNN
3. Extract the transcript content and metadata
4. Save each transcript as a text file with the format: `YYYY-MM-DD_transcript_title.txt`

Each transcript file includes metadata headers:
- Title
- Date
- Source
- URL

### Notes

- The script includes rate limiting to be respectful to the CNN website
- CSS selectors in the script may need adjustment based on changes to the CNN website structure
- The script handles pagination to download transcripts from multiple pages

### Integration with the Assistant

After downloading the transcripts, you can run the main ingestion process to index them:

```bash
# Navigate to the project root
cd ..

# Run the ingestion script
python ingest.py
```

This will process the downloaded transcripts, generate embeddings, and index them in both ChromaDB and Whoosh, making them available for the assistant to use when answering queries.
