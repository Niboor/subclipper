import logging
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import os
import time
from contextlib import contextmanager
import base64
import codecs
import sys

from .models import Video, Subtitle, ClipSettings
from subs.subs import (extract_subs, generate_video)

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, search_path: Path, font_path: Path):
        self.search_path = search_path
        self.font_path = font_path
        logger.info(f"Initialized VideoProcessor with search_path: {search_path}, font_path: {font_path}")

    def generate_clip(self, settings: ClipSettings) -> Tuple[Optional[Path], Optional[str]]:
        """Generate a video clip with the given settings."""
        try:
            logger.debug(f"Starting clip generation with settings: {settings}")
            errors = settings.validate()
            if errors:
                return None, str(errors)

            # Create a temporary directory that won't be automatically cleaned up
            tmp_dir = Path(tempfile.mkdtemp())
            output_clip = tmp_dir / 'clip.mp4'
            output_path = tmp_dir / f'clip.{settings.format}'

            err, ok = generate_video(
                start_time=settings.start_time,
                end_time=settings.end_time,
                output_clip=str(output_clip),
                output_path=str(output_path),
                custom_text=settings.text,
                caption=settings.caption,
                input_path=self.search_path.joinpath(settings.video_id),
                fps=20,  # fps
                crop=settings.crop,
                boomerang=settings.boomerang,
                resolution=settings.resolution,
                font=self.font_path,
                font_size=settings.font_size,
                fancy_colors=settings.colour,
                format_type=settings.format
            )

            if ok:
                return output_path, None
            return None, err
        except Exception as e:
            logger.exception("Failed to generate clip")
            raise