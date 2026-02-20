import os
import logging
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        import subprocess

        font = subprocess.check_output(
            ["fc-match", "sans", "-f", "%{family}"]
        ).decode().strip()

        self.search_path = Path(self._get_required_env('SEARCH_PATH'))
        self.show_name = self._get_required_env('SHOW_NAME')
        self.default_page_length = int(self._get_optional_env('DEFAULT_PAGE_LENGTH', '50'))
        self.font_name = font
        self.languages = self._get_optional_env('SUB_LANG', None)
        logger.info(f"Initialized Config with search_path: {self.search_path}, show_name: {self.show_name}, font_name: {self.font_name}")
        self._video_processor = None

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

    @property
    def video_processor(self):
        """Get the VideoProcessor instance, creating it if necessary."""
        if self._video_processor is None:
            from ..core.video_processor import VideoProcessor
            self._video_processor = VideoProcessor(self.search_path, self.font_name, self.languages)
            # Load videos on startup
            self._video_processor.load_videos()
        return self._video_processor