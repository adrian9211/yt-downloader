"""OAuth 2.0 authentication for YouTube Data API."""
import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


logger = logging.getLogger(__name__)

# OAuth 2.0 scopes required for YouTube Data API
SCOPES = [
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/youtube.force-ssl'  # For removing videos from playlists
]


def get_authenticated_service(
    credentials_file: str,
    token_file: str = "./data/token.json"
) -> Any:
    """
    Authenticate and return YouTube Data API service.
    
    Args:
        credentials_file: Path to OAuth 2.0 credentials JSON file
        token_file: Path to store/load the access token
        
    Returns:
        YouTube Data API service object
    """
    creds = None
    token_path = Path(token_file)
    
    # Load existing token if available
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            logger.info("Loaded existing credentials from token file")
        except Exception as e:
            logger.warning(f"Error loading token file: {e}")
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials...")
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.error(f"Error refreshing token: {e}")
                creds = None
        
        if not creds:
            logger.info("Starting OAuth flow...")
            if not Path(credentials_file).exists():
                raise FileNotFoundError(
                    f"OAuth credentials file not found: {credentials_file}\n"
                    "Please download your OAuth 2.0 credentials from Google Cloud Console.\n"
                    "See README.md for instructions."
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.info("OAuth authentication successful")
        
        # Save the credentials for the next run
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
        logger.info(f"Saved credentials to {token_file}")
    
    # Build and return the YouTube service
    try:
        service = build('youtube', 'v3', credentials=creds)
        logger.info("YouTube Data API service initialized")
        return service
    except Exception as e:
        logger.error(f"Error building YouTube service: {e}")
        raise


def revoke_token(token_file: str = "./data/token.json") -> bool:
    """
    Revoke the stored token (useful for re-authentication).
    
    Args:
        token_file: Path to the token file
        
    Returns:
        True if successful, False otherwise
    """
    token_path = Path(token_file)
    if not token_path.exists():
        logger.warning("No token file to revoke")
        return False
    
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.refresh_token:
            creds.revoke(Request())
            logger.info("Token revoked successfully")
        
        # Delete token file
        token_path.unlink()
        logger.info("Token file deleted")
        return True
    except Exception as e:
        logger.error(f"Error revoking token: {e}")
        return False


