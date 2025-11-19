# YouTube Watch Later Downloader

A local Python tool to automatically download all videos from your YouTube Watch Later playlist. Downloads videos in 720p or higher resolution, handles duplicates, retries failed downloads, and supports resuming interrupted sessions.

## Features

- ✅ **Automatic Playlist Fetching**: Retrieves all videos from your YouTube Watch Later playlist or any other playlist
- ✅ **Multiple Playlist Support**: Download from Watch Later or any of your custom playlists
- ✅ **High Quality Downloads**: Downloads videos in 720p or higher resolution (MP4 format preferred)
- ✅ **Concurrent Downloads**: Supports multiple simultaneous downloads (configurable)
- ✅ **Resume Support**: Skips already downloaded videos automatically
- ✅ **Retry Logic**: Automatically retries failed downloads with configurable attempts
- ✅ **Duplicate Handling**: Detects and skips videos that are already downloaded
- ✅ **Comprehensive Logging**: Detailed logs of all download activities
- ✅ **OAuth 2.0 Authentication**: Secure OAuth 2.0 authentication with YouTube Data API
- ✅ **Error Handling**: Gracefully handles unavailable, private, or deleted videos

## Requirements

- Python 3.7 or higher
- Internet connection
- YouTube account with Watch Later playlist
- Google Cloud project with OAuth 2.0 credentials

## Installation

1. **Clone or download this repository**

2. **Set up a virtual environment** (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Set up OAuth 2.0 credentials** (required for accessing Watch Later playlist):

### Step 1: Create a Google Cloud Project

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Note your project name for later

### Step 2: Enable YouTube Data API v3

1. In the Google Cloud Console, navigate to **APIs & Services** > **Library**
2. Search for "YouTube Data API v3"
3. Click on it and press **Enable**

### Step 3: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** > **Credentials**
2. Click **Create Credentials** > **OAuth client ID**
3. If prompted, configure the OAuth consent screen:
   - Choose **External** (unless you have a Google Workspace account)
   - Fill in the required information:
     - App name: "YouTube Watch Later Downloader" (or any name)
     - User support email: Your email
     - Developer contact: Your email
   - Click **Save and Continue**
   - On the Scopes page, click **Save and Continue** (no need to add scopes here)
   - **IMPORTANT**: On the Test users page, **add your Google account email** (the one you use for YouTube), then click **Save and Continue**
     - ⚠️ **You MUST add yourself as a test user, otherwise you'll get "access_denied" errors!**
   - Review and go back to dashboard
   
   **Note**: If you already created the OAuth consent screen but forgot to add yourself, go to **APIs & Services** > **OAuth consent screen** > **Test users** section and click **+ ADD USERS** to add your email.

4. Back in Credentials, click **Create Credentials** > **OAuth client ID**
5. Choose **Desktop app** as the application type
6. Give it a name (e.g., "YouTube Downloader")
7. Click **Create**
8. Click **Download JSON** to download your credentials
9. Save the downloaded file as `credentials.json` in the project root directory

### Step 4: First Run Authentication

1. Make sure your virtual environment is activated (if you created one):
   ```bash
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Run the tool for the first time:
   ```bash
   python3 run.py
   ```

2. Your browser will open automatically for OAuth authentication
3. Sign in with your Google account
4. Grant the required permissions (YouTube read access)
5. The tool will save your access token for future use

**Note**: The token is stored locally in `data/token.json` and will be automatically refreshed when needed.

## Configuration

Edit `config/settings.json` to customize the downloader:

```json
{
  "download_path": "./downloads",
  "resolution_preference": "720p",
  "min_resolution": "720p",
  "max_resolution": "1080p",
  "max_concurrent_downloads": 3,
  "retry_attempts": 3,
  "retry_delay_seconds": 5,
  "oauth_credentials_file": "./credentials.json",
  "oauth_token_file": "./data/token.json",
  "playlist_data_file": "./data/playlist.json",
  "log_file": "./data/download.log",
  "download_tracker_file": "./data/downloaded_videos.json",
  "auto_clean_watch_later": false,
  "resume_downloads": true,
  "format_preference": "mp4",
  "default_playlist_name": "Do obejrzenia"
}
```

### Configuration Options

- **download_path**: Directory where videos will be saved (supports `~` for home directory)
- **resolution_preference**: Preferred resolution (e.g., "720p", "1080p") - used for preference only
- **min_resolution**: Minimum acceptable resolution (default: "720p")
- **max_resolution**: Maximum resolution cap (default: "1080p") - **prevents 4K downloads**
- **max_concurrent_downloads**: Number of videos to download simultaneously (1-5 recommended)
- **retry_attempts**: Number of times to retry failed downloads
- **retry_delay_seconds**: Seconds to wait between retry attempts
- **oauth_credentials_file**: Path to your OAuth 2.0 credentials JSON file (from Google Cloud Console)
- **oauth_token_file**: Path where the access token will be stored (auto-generated)
- **playlist_data_file**: Where to cache playlist information
- **log_file**: Path to the log file
- **auto_clean_watch_later**: Automatically remove videos from Watch Later after download (requires additional setup)
- **resume_downloads**: Skip videos that are already downloaded
- **format_preference**: Preferred video format (mp4, webm, etc.)

## Usage

### Basic Usage

**Important**: Make sure your virtual environment is activated (if you created one):
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Run the downloader with default settings:

```bash
python3 run.py
```

Or alternatively:

```bash
python3 -m src.main
```

### Command Line Options

```bash
# Only fetch playlist without downloading
python3 run.py --fetch-only

# Only download from cached playlist (skip fetching)
python3 run.py --download-only

# Use custom config file
python3 run.py --config /path/to/custom/config.json

# List all available playlists
python3 run.py --list-playlists

# Download from a specific playlist (instead of Watch Later)
python3 run.py --playlist-id <PLAYLIST_ID>

# Example: Download from "Muzyka" playlist
python3 run.py --playlist-id PL1H29fb3JfEbTyxecYaWnQCooooAVGXPx
```

### Workflow

1. **First Run**: The tool will:
   - Fetch your Watch Later playlist (or specified playlist)
   - Save playlist data to `data/playlist.json`
   - Start downloading all videos

2. **Subsequent Runs**: The tool will:
   - Check for new videos in the playlist
   - Skip already downloaded videos (if `resume_downloads` is enabled)
   - Download only new videos

3. **Interrupted Downloads**: If the download is interrupted:
   - Run the tool again - it will automatically resume
   - Already downloaded videos will be skipped

### Downloading from Other Playlists

If Watch Later is empty or you want to download from a different playlist:

1. **List all available playlists**:
   ```bash
   python3 run.py --list-playlists
   ```

2. **Download from a specific playlist**:
   ```bash
   python3 run.py --playlist-id <PLAYLIST_ID>
   ```

   Example:
   ```bash
   # Download from "Muzyka" playlist (287 videos)
   python3 run.py --playlist-id PL1H29fb3JfEbTyxecYaWnQCooooAVGXPx
   ```

3. **You can combine options**:
   ```bash
   # Fetch playlist info only (no download)
   python3 run.py --playlist-id PL1H29fb3JfEbTyxecYaWnQCooooAVGXPx --fetch-only
   ```

## File Naming

Videos are saved with the format:
```
<index> - <video_title>.mp4
```

Example:
```
0001 - How to Build a Python CLI Tool.mp4
0002 - Advanced Python Techniques.mp4
```

Invalid filename characters are automatically sanitized.

## Logging

All activities are logged to `data/download.log` and also displayed in the console. The log includes:

- Start and end times
- Playlist fetching progress
- Download progress for each video
- Success/failure status
- Error messages
- Summary statistics

## Troubleshooting

### "Authentication required" or "Access forbidden" errors

- Make sure your `credentials.json` file is in the project root directory
- Verify that YouTube Data API v3 is enabled in your Google Cloud project
- Check that your OAuth consent screen is properly configured
- Try deleting `data/token.json` and re-authenticating
- Ensure you granted the required permissions during OAuth flow

### Videos not downloading

- Check your internet connection
- Verify the video is still available on YouTube
- Check the log file for specific error messages
- Try reducing `max_concurrent_downloads` if you're experiencing timeouts

### "No videos found in Watch Later"

- Make sure you have videos in your Watch Later playlist
- Verify you're authenticated with the correct Google account
- Check that the OAuth token is valid (delete `data/token.json` to re-authenticate)
- Ensure YouTube Data API v3 is enabled in your Google Cloud project

### Download quality issues

- Adjust `min_resolution` in config (e.g., "1080p" for higher quality)
- Note: Higher resolutions take longer to download and use more disk space

## Project Structure

```
youtube-downloader/
│
├── config/
│   └── settings.json          # Configuration file
│
├── data/
│   ├── playlist.json          # Cached playlist data
│   └── download.log           # Download logs
│
├── downloads/                 # Downloaded videos (created automatically)
│
├── src/
│   ├── __init__.py
│   ├── main.py               # Main entry point
│   ├── oauth_auth.py         # OAuth 2.0 authentication
│   ├── playlist_fetcher.py   # Playlist fetching logic (YouTube Data API)
│   ├── downloader.py         # Download logic with retry
│   └── utils.py              # Utility functions
│
├── credentials.json          # OAuth 2.0 credentials (download from Google Cloud Console)
├── data/
│   └── token.json            # OAuth access token (auto-generated)
├── venv/                     # Virtual environment (created during setup)
├── requirements.txt          # Python dependencies
├── run.py                    # Simple run script
└── README.md                 # This file
```

## Advanced Usage

### Automation with Cron (macOS/Linux)

To run automatically, add to your crontab:

```bash
# Run every day at 2 AM
0 2 * * * cd /path/to/yt-downloader && /usr/bin/python3 -m src.main >> /path/to/yt-downloader/data/cron.log 2>&1
```

### Automation with Task Scheduler (Windows)

1. Open Task Scheduler
2. Create a new task
3. Set trigger (e.g., daily at 2 AM)
4. Set action: `python.exe -m src.main`
5. Set working directory to the project folder

## Limitations

- Requires OAuth 2.0 setup with Google Cloud Console
- Cannot download videos that are region-restricted or require special permissions
- Auto-clean Watch Later feature requires OAuth scope with write permissions (included by default)
- Large playlists may take significant time to download
- YouTube Data API has quota limits (10,000 units per day by default, sufficient for most use cases)

## Privacy & Security

- This tool runs **locally** on your machine
- OAuth tokens are stored locally and encrypted
- No login credentials are stored in plain text
- All downloads are saved to your local machine
- OAuth tokens can be revoked at any time from your Google Account settings

## License

This tool is for personal use only. Respect YouTube's Terms of Service and copyright laws.

## Support

For issues or questions:
1. Check the log file (`data/download.log`) for detailed error messages
2. Verify your configuration settings
3. Ensure your OAuth credentials are set up correctly
4. Check that yt-dlp is up to date: `pip install --upgrade yt-dlp`
5. Verify YouTube Data API v3 is enabled in Google Cloud Console
6. If authentication fails, delete `data/token.json` and re-authenticate

## Acknowledgments

- Built with [yt-dlp](https://github.com/yt-dlp/yt-dlp) - an excellent YouTube downloader library

