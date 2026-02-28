"""Download YouTube videos using yt-dlp with retry logic and progress tracking."""
import yt_dlp
import logging
import time
import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed


logger = logging.getLogger(__name__)


class DownloadProgressHook:
    """Progress hook for yt-dlp to track download progress."""
    
    def __init__(self, video_title: str, logger: logging.Logger):
        self.video_title = video_title
        self.logger = logger
        self.status = None
    
    def __call__(self, d: Dict[str, Any]) -> None:
        if d['status'] == 'downloading':
            if 'total_bytes' in d:
                percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                self.logger.info(
                    f"Downloading '{self.video_title}': "
                    f"{percent:.1f}% ({d['downloaded_bytes']}/{d['total_bytes']} bytes)"
                )
            elif 'total_bytes_estimate' in d:
                percent = (d['downloaded_bytes'] / d['total_bytes_estimate']) * 100
                self.logger.info(
                    f"Downloading '{self.video_title}': "
                    f"{percent:.1f}% (estimated)"
                )
        elif d['status'] == 'finished':
            self.logger.info(f"Finished downloading '{self.video_title}'")
            self.status = 'finished'
        elif d['status'] == 'error':
            self.logger.error(f"Error downloading '{self.video_title}': {d.get('error', 'Unknown error')}")
            self.status = 'error'


def download_video(
    video: Dict[str, Any],
    download_path: str,
    min_resolution: str = "720p",
    max_resolution: str = "1080p",
    format_preference: str = "mp4",
    retry_attempts: int = 3,
    retry_delay: int = 5,
    index: Optional[int] = None,
    tracker_file: Optional[str] = None,
    cookies_file: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
    audio_only: bool = False,
    audio_format: str = "best"
) -> Dict[str, Any]:
    """
    Download a single video with retry logic.
    
    Args:
        video: Video dictionary with id, title, url
        download_path: Directory to save the video
        min_resolution: Minimum resolution (e.g., "720p")
        max_resolution: Maximum resolution (e.g., "1080p") - prevents 4K downloads
        format_preference: Preferred format (e.g., "mp4")
        retry_attempts: Number of retry attempts on failure
        retry_delay: Delay between retries in seconds
        index: Optional index for filename
        tracker_file: Path to download tracker file
        cookies_file: Path to Netscape formatted cookies file
        cookies_from_browser: Browser to extract cookies from (e.g., 'chrome', 'firefox')
        audio_only: If True, download only audio
        audio_format: Audio format preference (e.g. "best", "mp3", "m4a")
        
    Returns:
        Dictionary with download result: success, filepath, error
    """
    video_id = video.get('id', '')
    video_title = video.get('title', 'Unknown Title')
    video_url = video.get('url', f"https://www.youtube.com/watch?v={video_id}")
    
    # Sanitize filename
    try:
        from .utils import sanitize_filename, is_video_downloaded, mark_video_downloaded
    except ImportError:
        from utils import sanitize_filename, is_video_downloaded, mark_video_downloaded
    
    # Check tracker first (even if file doesn't exist locally)
    if tracker_file and is_video_downloaded(video_id, tracker_file):
        logger.info(f"Video already downloaded (tracked): {video_title}")
        return {
            'success': True,
            'filepath': None,  # File may have been deleted locally
            'skipped': True,
            'video_id': video_id,
            'video_title': video_title
        }
    
    # Create filename: <index> - <title>.<ext>
    # Note: Extension will be added/changed by yt-dlp
    if index is not None:
        filename_base = f"{index:04d} - {sanitize_filename(video_title)}"
    else:
        filename_base = f"{sanitize_filename(video_title)}"
    
    if audio_only:
        # For audio, the extension depends on what we convert it to
        # We'll rely on yt-dlp to name it correctly with the extension
        filename_tmpl = f"{filename_base}.%(ext)s"
        # We anticipate the final extension based on preference
        if audio_format and audio_format != 'best':
            final_ext = f".{audio_format}"
        else:
             # If best, it could be anything, but we'll try to guess or handle it
             pass
    else:
        filename_tmpl = f"{filename_base}.%(ext)s"
    
    # We construct the path for yt-dlp outtmpl
    outtmpl_path = str(Path(download_path) / filename_tmpl)
    
    # Check if file exists locally with expected extension
    # This is a bit tricky for audio since we don't know the final extension for sure yet if using "best"
    # But for video we expect mp4
    # Check if file exists locally with expected extension
    # If using audio conversion, we expect the target format
    expected_filepath = None
    
    if audio_only:
        if audio_format and audio_format != 'best':
             expected_filepath = (Path(download_path) / filename_base).with_suffix(f".{audio_format}")
    else:
         expected_filepath = (Path(download_path) / filename_base).with_suffix('.mp4')

    if expected_filepath and expected_filepath.exists():
        logger.info(f"Video file exists locally: {expected_filepath.name}")
        # Mark in tracker if not already there
        if tracker_file:
            try:
                file_size = expected_filepath.stat().st_size
                mark_video_downloaded(video_id, video_title, str(expected_filepath), tracker_file, file_size)
            except Exception as e:
                logger.warning(f"Could not update tracker: {e}")
        return {
            'success': True,
            'filepath': str(expected_filepath),
            'skipped': True,
            'video_id': video_id,
            'video_title': video_title
        }
    
    # Check for other common audio extensions if audio_only
    if audio_only:
        common_audio_exts = ['.mp3', '.m4a', '.webm', '.flac', '.wav', '.opus']
        for ext in common_audio_exts:
            check_path = (Path(download_path) / filename_base).with_suffix(ext)
            if check_path.exists():
                logger.info(f"Audio file exists locally: {check_path.name}")
                if tracker_file:
                    try:
                        file_size = check_path.stat().st_size
                        mark_video_downloaded(video_id, video_title, str(check_path), tracker_file, file_size)
                    except Exception:
                        pass
                return {
                    'success': True,
                    'filepath': str(check_path),
                    'skipped': True,
                    'video_id': video_id,
                    'video_title': video_title
                }
    
    # Configure format selector
    if audio_only:
        # Best audio quality
        format_selector = "bestaudio/best"
        logger.debug(f"Audio-only mode. Format selector: {format_selector}")
        
        # Add post-processors for audio conversion
        if audio_format and audio_format != 'best':
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': audio_format,
                'preferredquality': '192', # 192 is decent default, but for flac it is ignored (lossless)
            }]
            logger.debug(f"Adding audio post-processor for format: {audio_format}")
        else:
             postprocessors = []
    else:
        # Prefer: best video+audio merged, between min and max resolution, prefer mp4
        min_height = int(min_resolution.replace('p', ''))
        max_height = int(max_resolution.replace('p', ''))
        
        # Format selector: best video between min and max resolution + best audio
        format_selector = f"bestvideo[height>={min_height}][height<={max_height}]+bestaudio/best[height>={min_height}][height<={max_height}]"
        if format_preference.lower() == "mp4":
            format_selector += f"/best[ext=mp4][height<={max_height}]/best[height<={max_height}]"
        
        logger.debug(f"Format selector: {format_selector} (resolution: {min_resolution} to {max_resolution})")
    
    # Configure yt-dlp options
    ydl_opts = {
        'format': format_selector,
        'outtmpl': outtmpl_path,
        'quiet': False,
        'no_warnings': False,
        'progress_hooks': [DownloadProgressHook(video_title, logger)],
    }
    
    if audio_only and 'postprocessors' in locals() and postprocessors:
         ydl_opts['postprocessors'] = postprocessors
    
    if not audio_only:
        ydl_opts['merge_output_format'] = 'mp4'
    
    # Add authentication options
    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file
    if cookies_from_browser:
        ydl_opts['cookiesfrombrowser'] = (cookies_from_browser, None, None, None)
    
    # Retry logic
    last_error = None
    for attempt in range(1, retry_attempts + 1):
        try:
            logger.info(f"Downloading video {attempt}/{retry_attempts}: {video_title}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
            
            # Verify file was created
            # yt-dlp might add different extensions, so check for common ones
            # Verify file was created
            possible_files = []
            if audio_only:
                if audio_format and audio_format != 'best':
                    possible_files.append((Path(download_path) / filename_base).with_suffix(f".{audio_format}"))
                
                # Also check common extensions in case conversion failed or 'best' was used
                possible_files.extend([
                    (Path(download_path) / filename_base).with_suffix('.mp3'),
                    (Path(download_path) / filename_base).with_suffix('.m4a'),
                    (Path(download_path) / filename_base).with_suffix('.webm'),
                    (Path(download_path) / filename_base).with_suffix('.opus'),
                    (Path(download_path) / filename_base).with_suffix('.flac'),
                    (Path(download_path) / filename_base).with_suffix('.wav'),
                ])
            else:
                video_file_base = Path(download_path) / filename_base
                possible_files = [
                    video_file_base.with_suffix('.mp4'),
                    video_file_base.with_suffix('.webm'),
                    video_file_base.with_suffix('.mkv'),
                ]
            
            downloaded_file = None
            for possible_file in possible_files:
                if possible_file.exists():
                    downloaded_file = possible_file
                    break
            
            if downloaded_file:
                # Rename to .mp4 if needed (video only)
                if not audio_only and downloaded_file.suffix != '.mp4':
                    final_path = downloaded_file.with_suffix('.mp4')
                    downloaded_file.rename(final_path)
                    downloaded_file = final_path
                
                # Mark as downloaded in tracker
                if tracker_file:
                    try:
                        file_size = downloaded_file.stat().st_size
                        mark_video_downloaded(video_id, video_title, str(downloaded_file), tracker_file, file_size)
                        logger.debug(f"Marked video {video_id} as downloaded in tracker")
                    except Exception as e:
                        logger.warning(f"Could not update tracker: {e}")
                
                logger.info(f"Successfully downloaded: {downloaded_file.name}")
                return {
                    'success': True,
                    'filepath': str(downloaded_file),
                    'skipped': False,
                    'video_id': video_id,
                    'video_title': video_title
                }
            else:
                raise FileNotFoundError("Downloaded file not found after download")
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            last_error = error_msg
            
            # Check for specific error types
            if "Private video" in error_msg or "Video unavailable" in error_msg:
                logger.error(f"Video unavailable or private: {video_title}")
                return {
                    'success': False,
                    'filepath': None,
                    'error': 'Video unavailable or private',
                    'video_id': video_id,
                    'video_title': video_title
                }
            elif "Sign in" in error_msg or "authentication" in error_msg.lower():
                logger.error(f"Authentication required for: {video_title}")
                return {
                    'success': False,
                    'filepath': None,
                    'error': 'Authentication required',
                    'video_id': video_id,
                    'video_title': video_title
                }
            else:
                logger.warning(f"Download attempt {attempt} failed: {error_msg}")
                if attempt < retry_attempts:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    
        except Exception as e:
            last_error = str(e)
            logger.warning(f"Download attempt {attempt} failed with error: {e}")
            if attempt < retry_attempts:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
    
    # All retries failed
    logger.error(f"Failed to download after {retry_attempts} attempts: {video_title}")
    return {
        'success': False,
        'filepath': None,
        'error': last_error or 'Unknown error',
        'video_id': video_id,
        'video_title': video_title
    }


def download_playlist(
    videos: list,
    download_path: str,
    min_resolution: str = "720p",
    max_resolution: str = "1080p",
    format_preference: str = "mp4",
    max_concurrent: int = 3,
    retry_attempts: int = 3,
    retry_delay: int = 5,
    resume: bool = True,
    tracker_file: Optional[str] = None,
    cookies_file: Optional[str] = None,
    cookies_from_browser: Optional[str] = None,
    audio_only: bool = False,
    audio_format: str = "best"
) -> Dict[str, Any]:
    """
    Download multiple videos with concurrent downloads.
    
    Args:
        videos: List of video dictionaries
        download_path: Directory to save videos
        min_resolution: Minimum resolution
        max_resolution: Maximum resolution (prevents 4K downloads)
        format_preference: Preferred format
        max_concurrent: Maximum concurrent downloads
        retry_attempts: Number of retry attempts per video
        retry_delay: Delay between retries
        resume: Skip already downloaded videos
        tracker_file: Path to download tracker file
        cookies_file: Path to cookies file
        cookies_from_browser: Browser to extract cookies from
        audio_only: Download audio only
        audio_format: Audio format preference
        
    Returns:
        Dictionary with download statistics
    """
    logger.info(f"Starting download of {len(videos)} videos...")
    
    skipped_count = 0  # Initialize skipped count
    original_video_count = len(videos)

    # Filter out already downloaded videos if resume is enabled
    if resume:
        try:
            from .utils import get_downloaded_videos
        except ImportError:
            from utils import get_downloaded_videos
        # Use tracker file if provided, otherwise fall back to checking files
        if tracker_file:
            downloaded_ids = get_downloaded_videos(tracker_file, download_path)
        else:
            # Fallback: check local files only (backwards compatibility)
            download_dir = Path(download_path)
            downloaded_ids = set()
            if download_dir.exists():
                for file in download_dir.glob("*.mp4"):
                    filename = file.stem
                    video_id_match = re.search(r'([a-zA-Z0-9_-]{11})$', filename)
                    if video_id_match:
                        downloaded_ids.add(video_id_match.group(1))
                
                # If audio only, we also need to check common audio extensions
                if audio_only:
                     for file in download_dir.glob("*"):
                         if file.suffix in ['.mp3', '.m4a', '.webm', '.opus', '.flac', '.wav']:
                            filename = file.stem
                            video_id_match = re.search(r'([a-zA-Z0-9_-]{11})$', filename)
                            if video_id_match:
                                downloaded_ids.add(video_id_match.group(1))
        
        videos_to_download = [
            v for v in videos 
            if v.get('id', '') not in downloaded_ids
        ]
        skipped_count = len(videos) - len(videos_to_download)
        if skipped_count > 0:
            logger.info(f"Skipping {skipped_count} already downloaded videos (tracked)")
        videos = videos_to_download
    
    if not videos:
        logger.info("All videos are already downloaded!")
        return {
            'total': original_video_count,
            'successful': 0,
            'failed': 0,
            'skipped': skipped_count,
            'results': []
        }
    
    results = []
    successful = 0
    failed = 0
    skipped = 0
    
    # Download with thread pool for concurrency
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        # Submit all download tasks
        future_to_video = {
            executor.submit(
                download_video,
                video,
                download_path,
                min_resolution,
                max_resolution,
                format_preference,
                retry_attempts,
                retry_delay,
                video.get('index'),
                tracker_file,
                cookies_file,
                cookies_from_browser,
                audio_only,
                audio_format
            ): video
            for video in videos
        }
        
        # Process completed downloads
        for future in as_completed(future_to_video):
            video = future_to_video[future]
            try:
                result = future.result()
                results.append(result)
                
                if result.get('skipped'):
                    skipped += 1
                elif result.get('success'):
                    successful += 1
                else:
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Unexpected error downloading {video.get('title', 'Unknown')}: {e}")
                failed += 1
                results.append({
                    'success': False,
                    'video_id': video.get('id', ''),
                    'video_title': video.get('title', 'Unknown'),
                    'error': str(e)
                })
    
    logger.info(f"Download complete: {successful} successful, {failed} failed, {skipped} skipped")
    
    return {
        'total': original_video_count,
        'successful': successful,
        'failed': failed,
        'skipped': skipped + skipped_count,
        'results': results
    }

