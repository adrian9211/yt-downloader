"""Fetch YouTube playlists using YouTube Data API v3."""
import logging
import re
from typing import List, Dict, Any, Optional
from googleapiclient.errors import HttpError


logger = logging.getLogger(__name__)


def find_playlist_by_name(service: Any, playlist_name: str, case_sensitive: bool = False) -> Optional[Dict[str, Any]]:
    """
    Find a playlist by name (supports partial matching).
    
    Args:
        service: Authenticated YouTube Data API service
        playlist_name: Name of the playlist to find
        case_sensitive: Whether to match case exactly
        
    Returns:
        Playlist dictionary with id, title, and itemCount, or None if not found
    """
    logger.info(f"Searching for playlist: '{playlist_name}'")
    playlists = list_user_playlists(service)
    
    search_name = playlist_name if case_sensitive else playlist_name.lower()
    
    # Try exact match first
    for playlist in playlists:
        title = playlist['title'] if case_sensitive else playlist['title'].lower()
        if title == search_name:
            logger.info(f"Found exact match: '{playlist['title']}' (ID: {playlist['id']})")
            return playlist
    
    # Try partial match
    for playlist in playlists:
        title = playlist['title'] if case_sensitive else playlist['title'].lower()
        if search_name in title or title in search_name:
            logger.info(f"Found partial match: '{playlist['title']}' (ID: {playlist['id']})")
            return playlist
    
    logger.warning(f"Playlist '{playlist_name}' not found")
    return None


def list_user_playlists(service: Any) -> List[Dict[str, Any]]:
    """
    List all playlists for the authenticated user.
    
    Args:
        service: Authenticated YouTube Data API service
        
    Returns:
        List of playlist dictionaries with id, title, and itemCount
    """
    logger.info("Fetching user's playlists...")
    playlists = []
    next_page_token = None
    
    try:
        while True:
            request = service.playlists().list(
                part='snippet,contentDetails',
                mine=True,
                maxResults=50,
                pageToken=next_page_token
            )
            
            response = request.execute()
            
            if not response.get('items'):
                break
            
            for playlist in response['items']:
                playlist_data = {
                    'id': playlist['id'],
                    'title': playlist['snippet'].get('title', 'Unknown'),
                    'item_count': playlist['contentDetails'].get('itemCount', 0),
                    'description': playlist['snippet'].get('description', ''),
                }
                playlists.append(playlist_data)
            
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        logger.info(f"Found {len(playlists)} playlists")
        return playlists
        
    except HttpError as e:
        logger.error(f"Error listing playlists: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error listing playlists: {e}")
        return []


def fetch_playlist_by_id(service: Any, playlist_id: str) -> List[Dict[str, Any]]:
    """
    Fetch all videos from any YouTube playlist by ID.
    
    Args:
        service: Authenticated YouTube Data API service
        playlist_id: YouTube playlist ID
        
    Returns:
        List of video dictionaries with id, title, url, and duration
    """
    logger.info(f"Fetching playlist with ID: {playlist_id}")
    
    videos = []
    next_page_token = None
    
    try:
        while True:
            # Fetch playlist items
            request = service.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=playlist_id,
                maxResults=50,  # Maximum allowed by API
                pageToken=next_page_token
            )
            
            response = request.execute()
            
            logger.debug(f"API response: {len(response.get('items', []))} items in this page")
            
            if not response.get('items'):
                total_results = response.get('pageInfo', {}).get('totalResults', 0)
                if total_results == 0:
                    logger.warning("Playlist appears to be empty")
                break
            
            # Get video IDs to fetch details
            video_ids = [item['contentDetails']['videoId'] for item in response['items']]
            logger.info(f"Found {len(video_ids)} video IDs in this page")
            
            # Fetch video details in batch
            videos_response = service.videos().list(
                part='snippet,contentDetails,statistics',
                id=','.join(video_ids)
            ).execute()
            
            logger.debug(f"Video details response: {len(videos_response.get('items', []))} videos found")
            
            # Map video details to our format
            video_details = {
                vid['id']: vid for vid in videos_response.get('items', [])
            }
            
            if len(video_details) < len(video_ids):
                logger.warning(f"Only {len(video_details)} out of {len(video_ids)} videos had details (some may be private/deleted)")
            
            # Combine playlist item info with video details
            for idx, item in enumerate(response['items'], start=len(videos) + 1):
                video_id = item['contentDetails']['videoId']
                video_info = video_details.get(video_id)
                
                if not video_info:
                    logger.warning(f"Video details not found for ID: {video_id}")
                    continue
                
                # Parse duration (ISO 8601 format: PT1H2M10S)
                duration_str = video_info['contentDetails'].get('duration', 'PT0S')
                duration_seconds = parse_duration(duration_str)
                
                video_data = {
                    'index': idx,
                    'id': video_id,
                    'title': video_info['snippet'].get('title', 'Unknown Title'),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'duration': duration_seconds,
                    'uploader': video_info['snippet'].get('channelTitle', 'Unknown'),
                    'view_count': int(video_info['statistics'].get('viewCount', 0)),
                    'published_at': video_info['snippet'].get('publishedAt', ''),
                }
                videos.append(video_data)
                logger.debug(f"Extracted: {video_data['title']}")
            
            # Check for next page
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
            
            logger.info(f"Fetched {len(videos)} videos so far...")
        
        logger.info(f"Successfully fetched {len(videos)} videos from playlist")
        return videos
        
    except HttpError as e:
        logger.error(f"HTTP error while fetching playlist: {e}")
        if e.resp.status == 403:
            logger.error("Access forbidden. Check your OAuth scopes and credentials.")
        elif e.resp.status == 404:
            logger.error("Playlist not found. Check the playlist ID.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while fetching playlist: {e}")
        raise


def get_watch_later_playlist_id(service: Any) -> Optional[str]:
    """
    Get the Watch Later playlist ID for the authenticated user.
    
    Args:
        service: Authenticated YouTube Data API service
        
    Returns:
        Watch Later playlist ID, or None if not found
    """
    try:
        # Method 1: Try to get from channel's relatedPlaylists
        channels_response = service.channels().list(
            part='contentDetails',
            mine=True
        ).execute()
        
        if channels_response.get('items'):
            channel = channels_response['items'][0]
            playlists = channel.get('contentDetails', {}).get('relatedPlaylists', {})
            
            # Watch Later playlist ID from relatedPlaylists
            watch_later_id = playlists.get('watchLater')
            
            if watch_later_id:
                logger.info(f"Found Watch Later playlist ID from channel: {watch_later_id}")
                return watch_later_id
        
        # Method 2: Watch Later playlist has a special ID "WL"
        # Try to verify it exists by checking if we can access it
        logger.info("Trying special Watch Later playlist ID: WL")
        try:
            test_response = service.playlistItems().list(
                part='id',
                playlistId='WL',
                maxResults=1
            ).execute()
            logger.info("Successfully accessed Watch Later playlist with ID: WL")
            return 'WL'
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning("Watch Later playlist 'WL' not accessible")
            else:
                logger.warning(f"Error accessing 'WL' playlist: {e}")
        
        # Method 3: Search for it in user's playlists
        logger.info("Searching for Watch Later playlist in user's playlists...")
        playlists_response = service.playlists().list(
            part='id,snippet',
            mine=True,
            maxResults=50
        ).execute()
        
        for playlist in playlists_response.get('items', []):
            title = playlist.get('snippet', {}).get('title', '').lower()
            if 'watch later' in title or playlist['id'] == 'WL':
                playlist_id = playlist['id']
                logger.info(f"Found Watch Later playlist: {playlist_id}")
                return playlist_id
        
        logger.error("Watch Later playlist not found using any method")
        return None
            
    except HttpError as e:
        logger.error(f"HTTP error getting Watch Later playlist ID: {e}")
        if e.resp.status == 403:
            logger.error("Access forbidden. Check OAuth scopes - you need youtube.readonly scope.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting Watch Later playlist ID: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


def fetch_watch_later_playlist(service: Any, playlist_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch all videos from YouTube Watch Later playlist using YouTube Data API.
    Tries multiple methods to find the Watch Later playlist.
    
    Args:
        service: Authenticated YouTube Data API service
        playlist_name: Optional playlist name to search for (e.g., "Do obejrzenia", "Watch Later")
        
    Returns:
        List of video dictionaries with id, title, url, and duration
    """
    logger.info("Starting to fetch Watch Later playlist...")
    
    playlist_id = None
    
    # Method 1: Try common Watch Later names first (before trying WL)
    common_names = ["Do obejrzenia", "Watch Later", "À regarder", "Zu sehen", "Para ver"]
    if playlist_name:
        # If specific name provided, try it first
        common_names.insert(0, playlist_name)
    
    for name in common_names:
        logger.info(f"Trying to find playlist by name: '{name}'")
        playlist = find_playlist_by_name(service, name)
        if playlist and playlist['item_count'] > 0:
            playlist_id = playlist['id']
            logger.info(f"Found '{playlist['title']}' with {playlist['item_count']} items")
            break
    
    # Method 2: Try to get from channel's relatedPlaylists (WL)
    if not playlist_id:
        logger.info("Trying to get Watch Later from channel's relatedPlaylists...")
        playlist_id = get_watch_later_playlist_id(service)
    
    if not playlist_id:
        logger.error("Could not retrieve Watch Later playlist ID")
        logger.info("Try using --playlist-name or --playlist-id to specify a playlist")
        return []
    
    videos = []
    next_page_token = None
    
    try:
        while True:
            # Fetch playlist items
            request = service.playlistItems().list(
                part='snippet,contentDetails',
                playlistId=playlist_id,
                maxResults=50,  # Maximum allowed by API
                pageToken=next_page_token
            )
            
            response = request.execute()
            
            # Log full response for debugging
            logger.info(f"PlaylistItems API response: pageInfo={response.get('pageInfo')}, totalResults={response.get('pageInfo', {}).get('totalResults', 'N/A')}")
            logger.debug(f"API response: {len(response.get('items', []))} items in this page")
            
            if not response.get('items'):
                total_results = response.get('pageInfo', {}).get('totalResults', 0)
                if total_results == 0:
                    logger.warning("Playlist appears to be empty according to API (totalResults=0)")
                    logger.info("Note: If you see videos in YouTube web interface, they might be in a different playlist or require different permissions")
                else:
                    logger.warning(f"API reports {total_results} total items but returned 0 items - possible API issue")
                break
            
            # Get video IDs to fetch details
            video_ids = [item['contentDetails']['videoId'] for item in response['items']]
            logger.info(f"Found {len(video_ids)} video IDs in this page")
            
            # Fetch video details in batch
            videos_response = service.videos().list(
                part='snippet,contentDetails,statistics',
                id=','.join(video_ids)
            ).execute()
            
            logger.debug(f"Video details response: {len(videos_response.get('items', []))} videos found")
            
            # Map video details to our format
            video_details = {
                vid['id']: vid for vid in videos_response.get('items', [])
            }
            
            if len(video_details) < len(video_ids):
                logger.warning(f"Only {len(video_details)} out of {len(video_ids)} videos had details (some may be private/deleted)")
            
            # Combine playlist item info with video details
            for idx, item in enumerate(response['items'], start=len(videos) + 1):
                video_id = item['contentDetails']['videoId']
                video_info = video_details.get(video_id)
                
                if not video_info:
                    logger.warning(f"Video details not found for ID: {video_id}")
                    continue
                
                # Parse duration (ISO 8601 format: PT1H2M10S)
                duration_str = video_info['contentDetails'].get('duration', 'PT0S')
                duration_seconds = parse_duration(duration_str)
                
                video_data = {
                    'index': idx,
                    'id': video_id,
                    'title': video_info['snippet'].get('title', 'Unknown Title'),
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'duration': duration_seconds,
                    'uploader': video_info['snippet'].get('channelTitle', 'Unknown'),
                    'view_count': int(video_info['statistics'].get('viewCount', 0)),
                    'published_at': video_info['snippet'].get('publishedAt', ''),
                }
                videos.append(video_data)
                logger.debug(f"Extracted: {video_data['title']}")
            
            # Check for next page
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
            
            logger.info(f"Fetched {len(videos)} videos so far...")
        
        logger.info(f"Successfully fetched {len(videos)} videos from Watch Later playlist")
        return videos
        
    except HttpError as e:
        logger.error(f"HTTP error while fetching playlist: {e}")
        if e.resp.status == 403:
            logger.error("Access forbidden. Check your OAuth scopes and credentials.")
        elif e.resp.status == 401:
            logger.error("Authentication failed. Please re-authenticate.")
        raise
    except Exception as e:
        logger.error(f"Unexpected error while fetching playlist: {e}")
        raise


def parse_duration(duration_str: str) -> int:
    """
    Parse ISO 8601 duration string to seconds.
    
    Args:
        duration_str: ISO 8601 duration (e.g., "PT1H2M10S")
        
    Returns:
        Duration in seconds
    """
    # Remove PT prefix
    duration_str = duration_str.replace('PT', '')
    
    # Extract hours, minutes, seconds
    hours_match = re.search(r'(\d+)H', duration_str)
    minutes_match = re.search(r'(\d+)M', duration_str)
    seconds_match = re.search(r'(\d+)S', duration_str)
    
    hours = int(hours_match.group(1)) if hours_match else 0
    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = int(seconds_match.group(1)) if seconds_match else 0
    
    return hours * 3600 + minutes * 60 + seconds


def remove_video_from_watch_later(
    service: Any,
    video_id: str
) -> bool:
    """
    Remove a video from Watch Later playlist.
    
    Args:
        service: Authenticated YouTube Data API service
        video_id: YouTube video ID to remove
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get Watch Later playlist ID
        playlist_id = get_watch_later_playlist_id(service)
        if not playlist_id:
            logger.error("Could not retrieve Watch Later playlist ID")
            return False
        
        # Find the playlist item for this video
        request = service.playlistItems().list(
            part='id',
            playlistId=playlist_id,
            videoId=video_id,
            maxResults=1
        )
        
        response = request.execute()
        
        if not response.get('items'):
            logger.warning(f"Video {video_id} not found in Watch Later playlist")
            return False
        
        playlist_item_id = response['items'][0]['id']
        
        # Delete the playlist item
        service.playlistItems().delete(id=playlist_item_id).execute()
        
        logger.info(f"Removed video {video_id} from Watch Later playlist")
        return True
        
    except HttpError as e:
        logger.error(f"Error removing video from Watch Later: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
