"""Main entry point for YouTube Watch Later downloader."""
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

try:
    from .utils import (
        load_config,
        setup_logging,
        save_playlist_data,
        load_playlist_data
    )
    from .oauth_auth import get_authenticated_service
    from .playlist_fetcher import fetch_watch_later_playlist, remove_video_from_watch_later
    from .downloader import download_playlist
except ImportError:
    # Allow running as script
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from utils import (
        load_config,
        setup_logging,
        save_playlist_data,
        load_playlist_data
    )
    from oauth_auth import get_authenticated_service
    from playlist_fetcher import fetch_watch_later_playlist, remove_video_from_watch_later
    from downloader import download_playlist


def main():
    """Main function to run the YouTube Watch Later downloader."""
    parser = argparse.ArgumentParser(
        description='Download videos from YouTube Watch Later playlist'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='./config/settings.json',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--fetch-only',
        action='store_true',
        help='Only fetch playlist, do not download'
    )
    parser.add_argument(
        '--download-only',
        action='store_true',
        help='Only download from cached playlist, do not fetch'
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please create a configuration file at ./config/settings.json")
        sys.exit(1)
    
    # Setup logging
    logger = setup_logging(config['log_file'])
    logger.info("=" * 60)
    logger.info("YouTube Watch Later Downloader - Starting")
    logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Authenticate with YouTube API
    youtube_service = None
    if not args.download_only:
        try:
            logger.info("Authenticating with YouTube Data API...")
            youtube_service = get_authenticated_service(
                credentials_file=config.get('oauth_credentials_file', './credentials.json'),
                token_file=config.get('oauth_token_file', './data/token.json')
            )
            logger.info("Authentication successful")
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            logger.error("Please ensure you have set up OAuth credentials. See README.md for instructions.")
            sys.exit(1)
    
    # Fetch playlist
    playlist_data = []
    
    if not args.download_only:
        try:
            logger.info("Fetching Watch Later playlist...")
            playlist_data = fetch_watch_later_playlist(youtube_service)
            
            if not playlist_data:
                logger.warning("No videos found in Watch Later playlist")
                sys.exit(0)
            
            # Save playlist data
            save_playlist_data(playlist_data, config['playlist_data_file'])
            logger.info(f"Saved {len(playlist_data)} videos to {config['playlist_data_file']}")
            
        except Exception as e:
            logger.error(f"Error fetching playlist: {e}")
            if args.fetch_only:
                sys.exit(1)
            # Try to load cached playlist
            logger.info("Attempting to load cached playlist data...")
            playlist_data = load_playlist_data(config['playlist_data_file'])
            if not playlist_data:
                logger.error("No cached playlist data available. Cannot proceed.")
                sys.exit(1)
    else:
        # Load cached playlist
        playlist_data = load_playlist_data(config['playlist_data_file'])
        if not playlist_data:
            logger.error("No cached playlist data found. Run without --download-only first.")
            sys.exit(1)
        logger.info(f"Loaded {len(playlist_data)} videos from cached playlist")
    
    if args.fetch_only:
        logger.info("Fetch-only mode: Exiting without downloading")
        logger.info(f"Found {len(playlist_data)} videos in Watch Later playlist")
        sys.exit(0)
    
    # Download videos
    try:
        logger.info("Starting download process...")
        download_stats = download_playlist(
            videos=playlist_data,
            download_path=config['download_path'],
            min_resolution=config.get('min_resolution', '720p'),
            format_preference=config.get('format_preference', 'mp4'),
            max_concurrent=config.get('max_concurrent_downloads', 3),
            retry_attempts=config.get('retry_attempts', 3),
            retry_delay=config.get('retry_delay_seconds', 5),
            resume=config.get('resume_downloads', True)
        )
        
        # Log summary
        logger.info("=" * 60)
        logger.info("Download Summary:")
        logger.info(f"  Total videos: {download_stats['total']}")
        logger.info(f"  Successful: {download_stats['successful']}")
        logger.info(f"  Failed: {download_stats['failed']}")
        logger.info(f"  Skipped (already downloaded): {download_stats['skipped']}")
        logger.info("=" * 60)
        
        # Log failed downloads
        failed_videos = [
            r for r in download_stats['results']
            if not r.get('success', False) and not r.get('skipped', False)
        ]
        if failed_videos:
            logger.warning("Failed downloads:")
            for result in failed_videos:
                logger.warning(
                    f"  - {result.get('video_title', 'Unknown')}: "
                    f"{result.get('error', 'Unknown error')}"
                )
        
        # Auto-clean Watch Later if enabled
        if config.get('auto_clean_watch_later', False) and youtube_service:
            logger.info("Auto-clean enabled: Removing downloaded videos from Watch Later...")
            cleaned_count = 0
            for result in download_stats['results']:
                if result.get('success') and not result.get('skipped'):
                    video_id = result.get('video_id')
                    if video_id and remove_video_from_watch_later(youtube_service, video_id):
                        cleaned_count += 1
            logger.info(f"Removed {cleaned_count} videos from Watch Later")
        
        logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.warning("Download interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during download: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

