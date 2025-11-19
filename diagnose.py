#!/usr/bin/env python3
"""Diagnostic script to check YouTube API connection and playlists."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from oauth_auth import get_authenticated_service
from utils import load_config, setup_logging

def main():
    config = load_config()
    logger = setup_logging(config['log_file'])
    
    try:
        # Authenticate
        service = get_authenticated_service(
            credentials_file=config.get('oauth_credentials_file', './credentials.json'),
            token_file=config.get('oauth_token_file', './data/token.json')
        )
        
        # Get channel info
        logger.info("=" * 60)
        logger.info("DIAGNOSTIC: Checking authenticated account...")
        logger.info("=" * 60)
        
        channels_response = service.channels().list(
            part='snippet,contentDetails',
            mine=True
        ).execute()
        
        if channels_response.get('items'):
            channel = channels_response['items'][0]
            channel_title = channel['snippet'].get('title', 'Unknown')
            channel_id = channel['id']
            logger.info(f"Authenticated as: {channel_title} (ID: {channel_id})")
            
            # Check related playlists
            playlists = channel.get('contentDetails', {}).get('relatedPlaylists', {})
            logger.info(f"\nRelated Playlists:")
            for key, value in playlists.items():
                logger.info(f"  {key}: {value}")
            
            # Note: watchLater might not appear in relatedPlaylists if empty or if YouTube changed the API
            logger.info(f"\nNOTE: If 'watchLater' is not listed above, it might be because:")
            logger.info(f"  1. The playlist is empty")
            logger.info(f"  2. YouTube API structure changed")
            logger.info(f"  3. The playlist needs to be accessed differently")
            
            # Check Watch Later specifically
            watch_later_id = playlists.get('watchLater')
            if watch_later_id:
                logger.info(f"\nWatch Later ID from channel: {watch_later_id}")
                
                # Try to get items
                try:
                    items_response = service.playlistItems().list(
                        part='snippet',
                        playlistId=watch_later_id,
                        maxResults=5
                    ).execute()
                    
                    total = items_response.get('pageInfo', {}).get('totalResults', 0)
                    logger.info(f"Watch Later playlist has {total} items")
                    
                    if items_response.get('items'):
                        logger.info("\nFirst few items:")
                        for item in items_response['items'][:3]:
                            title = item['snippet'].get('title', 'Unknown')
                            video_id = item['snippet'].get('resourceId', {}).get('videoId', 'N/A')
                            logger.info(f"  - {title} (ID: {video_id})")
                except Exception as e:
                    logger.error(f"Error accessing Watch Later: {e}")
            else:
                logger.warning(f"\n'watchLater' key NOT found in relatedPlaylists!")
                logger.info(f"This is unusual - Watch Later should always be present.")
            
            # Also try the "WL" ID
            logger.info(f"\nTrying special 'WL' playlist ID...")
            try:
                items_response = service.playlistItems().list(
                    part='snippet,contentDetails',
                    playlistId='WL',
                    maxResults=5
                ).execute()
                
                total = items_response.get('pageInfo', {}).get('totalResults', 0)
                logger.info(f"'WL' playlist has {total} items")
                logger.info(f"Full response keys: {list(items_response.keys())}")
                logger.info(f"Response: {items_response}")
                
                if items_response.get('items'):
                    logger.info("\nFirst few items from 'WL':")
                    for item in items_response['items'][:3]:
                        title = item['snippet'].get('title', 'Unknown')
                        # Try both resourceId and contentDetails
                        video_id = (item.get('contentDetails', {}) or 
                                   item.get('snippet', {}).get('resourceId', {})).get('videoId', 'N/A')
                        logger.info(f"  - {title} (ID: {video_id})")
                        logger.info(f"    Item keys: {list(item.keys())}")
            except Exception as e:
                logger.error(f"Error accessing 'WL' playlist: {e}")
                import traceback
                logger.error(traceback.format_exc())
            
            # List user's playlists
            logger.info(f"\nListing user's playlists...")
            playlists_response = service.playlists().list(
                part='snippet,contentDetails',
                mine=True,
                maxResults=50
            ).execute()
            
            logger.info(f"Found {len(playlists_response.get('items', []))} playlists:")
            for playlist in playlists_response.get('items', [])[:20]:
                title = playlist['snippet'].get('title', 'Unknown')
                playlist_id = playlist['id']
                item_count = playlist['contentDetails'].get('itemCount', 0)
                logger.info(f"  - {title} (ID: {playlist_id}, Items: {item_count})")
                # Check if this might be Watch Later
                if 'watch' in title.lower() and 'later' in title.lower():
                    logger.info(f"    *** This might be your Watch Later playlist! ***")
                    # Try to get items from it
                    try:
                        test_items = service.playlistItems().list(
                            part='snippet',
                            playlistId=playlist_id,
                            maxResults=3
                        ).execute()
                        logger.info(f"    This playlist has {test_items.get('pageInfo', {}).get('totalResults', 0)} items")
                    except:
                        pass
        
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)

if __name__ == '__main__':
    main()

