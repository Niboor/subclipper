import os
import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        self.search_path = self._get_required_env('SEARCH_PATH')
        self.show_name = self._get_required_env('SHOW_NAME')
        self.font_path = self._find_font()
        logger.info(f"Initialized Config with search_path: {self.search_path}, show_name: {self.show_name}, font_path: {self.font_path}")
        self._video_processor = None
        
    def _get_required_env(self, name: str) -> Path:
        """Get a required environment variable and convert it to a Path."""
        value = os.getenv(name)
        if value is None:
            logger.error(f"{name} has not been configured. Set the {name} env var")
            sys.exit(4)
        return Path(value)
        
    def _find_font(self) -> Path:
        """Find a suitable font for subtitle rendering."""
        from matplotlib import font_manager
        font = font_manager.findfont('')  # Get a fallback font
        return Path(font)
        
    @property
    def video_processor(self):
        """Get the VideoProcessor instance, creating it if necessary."""
        if self._video_processor is None:
            from ..core.video_processor import VideoProcessor
            self._video_processor = VideoProcessor(self.search_path, self.font_path)
            # Load videos on startup
            self._video_processor.load_videos()
        return self._video_processor 