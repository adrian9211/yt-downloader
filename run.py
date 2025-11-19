#!/usr/bin/env python3
"""Simple entry point script for the YouTube Watch Later downloader."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from main import main

if __name__ == '__main__':
    main()


