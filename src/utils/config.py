import os
import logging
from pathlib import Path
import sys
from ..core.video_processor import VideoProcessor
from ..core.subtitle_indexer import SubtitleIndexer

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        self.search_path = Path(self._get_required_env('SEARCH_PATH'))
        self.sqlite_path = self._get_optional_env('SQLITE_PATH', ':memory:')
        self.default_page_length = int(self._get_optional_env('DEFAULT_PAGE_LENGTH', '50'))
        self.font_path = self._find_font()
        logger.info(f"Initialized Config with search_path: {self.search_path}, font_path: {self.font_path}")
        self._video_processor = None
        self.subtitle_indexer = SubtitleIndexer(self.search_path, self.sqlite_path)
        
    def _get_required_env(self, name: str) -> str:
        """Get a required environment variable. If it is not present, the program will panic."""
        value = os.getenv(name)
        if value is None:
            logger.error(f"{name} has not been configured. Set the {name} env var")
            sys.exit(4)
        return value

    def _get_optional_env(self, name: str, default: str) -> str:
        """Get an optional environment variable. If it is not present, use the default value instead."""
        value = os.getenv(name)
        if value is None:
            return default
        return value
        
    def _find_font(self) -> Path:
        """Find a suitable font for subtitle rendering."""
        from matplotlib import font_manager
        font = font_manager.findfont('')  # Get a fallback font
        return Path(font)
        
    @property
    def video_processor(self):
        """Get the VideoProcessor instance, creating it if necessary."""
        if self._video_processor is None:
            self._video_processor = VideoProcessor(self.search_path, self.font_path)
        return self._video_processor