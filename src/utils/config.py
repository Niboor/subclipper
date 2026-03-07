import os
import logging
from pathlib import Path
import sys
from typing import TypeVar
from ..core.video_processor import VideoProcessor
from ..core.subtitle_indexer import SubtitleIndexer
import tempfile

logger = logging.getLogger(__name__)

class Config:
    def __init__(self):
        import subprocess

        font = subprocess.check_output(
            ["fc-match", "sans", "-f", "%{family}"]
        ).decode().strip()

        self.search_path = Path(self._get_required_env('SEARCH_PATH'))
        self.thumbnail_path = Path(self._get_optional_env('THUMBNAIL_PATH', tempfile.mkdtemp()))
        self.db_path = self._get_optional_env('DB_PATH', '')
        self.default_page_length = int(self._get_optional_env('DEFAULT_PAGE_LENGTH', '50'))
        self.font_name = font
        self.languages = self._get_optional_env('SUB_LANG', None)
        self.single_show_name = self._get_optional_env('SINGLE_SHOW_NAME', None)
        logger.info(f"Initialized Config with search_path: {self.search_path}, db_path: {self.db_path}, font_name: {self.font_name}")
        self._video_processor = None
        self.subtitle_indexer = SubtitleIndexer(self.search_path, self.db_path, self.languages)

    def _get_required_env(self, name: str) -> str:
        """Get a required environment variable. If it is not present, the program will panic."""
        value = os.getenv(name)
        if value is None:
            logger.error(f"{name} has not been configured. Set the {name} env var")
            sys.exit(4)
        return value

    N = TypeVar('N')

    def _get_optional_env(self, name: str, default: N) -> str | N:
        """Get an optional environment variable. If it is not present, use the default value instead."""
        value = os.getenv(name)
        if value is None:
            return default
        return value

    @property
    def video_processor(self):
        """Get the VideoProcessor instance, creating it if necessary."""
        if self._video_processor is None:
            self._video_processor = VideoProcessor(self.search_path, self.thumbnail_path, self.font_name, self.languages)
        return self._video_processor