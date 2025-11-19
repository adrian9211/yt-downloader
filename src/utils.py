"""Utility functions for the YouTube Watch Later downloader."""
import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


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


def get_downloaded_videos(download_path: str) -> set:
    """
    Get set of already downloaded video IDs from filenames.
    
    Args:
        download_path: Path to downloads directory
        
    Returns:
        Set of video IDs that have been downloaded
    """
    download_dir = Path(download_path)
    if not download_dir.exists():
        return set()
    
    downloaded = set()
    for file in download_dir.glob("*.mp4"):
        # Extract video ID from filename if present
        # Format: <index> - <title>_<video_id>.mp4 or similar
        filename = file.stem
        # Try to find YouTube video ID pattern (11 characters)
        video_id_match = re.search(r'([a-zA-Z0-9_-]{11})$', filename)
        if video_id_match:
            downloaded.add(video_id_match.group(1))
    
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


