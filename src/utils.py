"""Utility functions for the YouTube Watch Later downloader."""
import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, Any, Optional
import threading

_tracker_lock = threading.Lock()


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize a filename by removing invalid characters and limiting length.
    
    Args:
        filename: The original filename
        max_length: Maximum length for the filename
        
    Returns:
        Sanitized filename safe for filesystem
    """
    # Remove invalid characters for filenames
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    # Ensure it's not empty
    if not sanitized:
        sanitized = "video"
    
    return sanitized


def setup_logging(log_file: str) -> logging.Logger:
    """
    Set up logging to both file and console.
    
    Args:
        log_file: Path to the log file
        
    Returns:
        Configured logger instance
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


def load_config(config_path: str = "./config/settings.json") -> Dict[str, Any]:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to the configuration file
        
    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Expand user path for download_path
    if 'download_path' in config:
        config['download_path'] = os.path.expanduser(config['download_path'])
    
    # Ensure download directory exists
    Path(config['download_path']).mkdir(parents=True, exist_ok=True)
    
    return config


def save_playlist_data(playlist_data: list, data_file: str) -> None:
    """
    Save playlist data to JSON file.
    
    Args:
        playlist_data: List of video dictionaries
        data_file: Path to save the data
    """
    data_path = Path(data_file)
    data_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(playlist_data, f, indent=2, ensure_ascii=False)


def load_playlist_data(data_file: str) -> list:
    """
    Load playlist data from JSON file.
    
    Args:
        data_file: Path to the data file
        
    Returns:
        List of video dictionaries, or empty list if file doesn't exist
    """
    data_path = Path(data_file)
    
    if not data_path.exists():
        return []
    
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_download_tracker(tracker_file: str) -> Dict[str, Dict[str, Any]]:
    """
    Load the download tracker database.
    
    Args:
        tracker_file: Path to the tracker JSON file
        
    Returns:
        Dictionary mapping video_id to download info
    """
    tracker_path = Path(tracker_file)
    if not tracker_path.exists():
        return {}
    
    try:
        with open(tracker_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Error loading download tracker: {e}")
        return {}


def save_download_tracker(tracker: Dict[str, Dict[str, Any]], tracker_file: str) -> None:
    """
    Save the download tracker database.
    
    Args:
        tracker: Dictionary mapping video_id to download info
        tracker_file: Path to the tracker JSON file
    """
    tracker_path = Path(tracker_file)
    tracker_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Atomic write: write to temp file then rename with os.replace
    # This prevents the file from being empty/corrupt if the process crashes during write
    # or if another process reads it while it's being written
    temp_file = tracker_path.with_suffix('.tmp')
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(tracker, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, tracker_path)
    except Exception as e:
        if temp_file.exists():
            try:
                os.remove(temp_file)
            except OSError:
                pass
        raise e


def mark_video_downloaded(
    video_id: str,
    video_title: str,
    filepath: str,
    tracker_file: str,
    file_size: Optional[int] = None
) -> None:
    """
    Mark a video as downloaded in the tracker.
    
    Args:
        video_id: YouTube video ID
        video_title: Video title
        filepath: Path where the file was saved
        tracker_file: Path to the tracker JSON file
        file_size: Optional file size in bytes
    """
    with _tracker_lock:
        tracker = load_download_tracker(tracker_file)
        
        tracker[video_id] = {
            'video_id': video_id,
            'title': video_title,
            'filepath': filepath,
            'download_date': datetime.now().isoformat(),
            'file_size': file_size,
            'status': 'downloaded'
        }
        
        save_download_tracker(tracker, tracker_file)


def is_video_downloaded(video_id: str, tracker_file: str) -> bool:
    """
    Check if a video has been downloaded (according to tracker).
    
    Args:
        video_id: YouTube video ID
        tracker_file: Path to the tracker JSON file
        
    Returns:
        True if video is in tracker, False otherwise
    """
    tracker = load_download_tracker(tracker_file)
    return video_id in tracker and tracker[video_id].get('status') == 'downloaded'


def get_downloaded_videos(tracker_file: str, download_path: Optional[str] = None) -> set:
    """
    Get set of already downloaded video IDs from the tracker.
    Optionally also checks local files for backwards compatibility.
    
    Args:
        tracker_file: Path to the tracker JSON file
        download_path: Optional path to downloads directory (for backwards compatibility)
        
    Returns:
        Set of video IDs that have been downloaded
    """
    tracker = load_download_tracker(tracker_file)
    downloaded = set()
    
    # Get from tracker
    for video_id, info in tracker.items():
        if info.get('status') == 'downloaded':
            downloaded.add(video_id)
    
    # Also check local files for backwards compatibility (if download_path provided)
    if download_path:
        download_dir = Path(download_path)
        if download_dir.exists():
            for file in download_dir.glob("*.mp4"):
                filename = file.stem
                # Try to find YouTube video ID pattern (11 characters)
                video_id_match = re.search(r'([a-zA-Z0-9_-]{11})$', filename)
                if video_id_match:
                    video_id = video_id_match.group(1)
                    if video_id not in downloaded:
                        # Found a file that's not in tracker - add it
                        downloaded.add(video_id)
                        # Optionally update tracker (but we don't have title info here)
    
    return downloaded


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


