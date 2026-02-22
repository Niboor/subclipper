import logging
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import os
import time
from contextlib import contextmanager

from .models import Video, Subtitle, ClipSettings
from sub2clip.sub2clip import generate
from sub2clip.generation import (ClipSettings as SubSettings, TextStyle, VideoFormat)
from sub2clip.subtitles import (Subtitle as SSubtitle)

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, search_path: Path, font_name: str, languages: list[str]):
        self.search_path = search_path
        self.font_name = font_name
        self.languages = languages
        logger.info(f"Initialized VideoProcessor with search_path: {search_path}, font_name: {font_name}, language filter: {languages}")

    def generate_clip(self, settings: ClipSettings, subs: list[SSubtitle]) -> Tuple[Optional[Path], Optional[str]]:
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

            style = TextStyle(font=self.font_name, font_size=settings.font_size)

            start_time_ms = int(settings.start_time * 1000)
            end_time_ms = int(settings.end_time * 1000)
            clip_settings = SubSettings(
                input_path=self.search_path.joinpath(settings.video_id),
                clip_path=output_clip,
                output_path=output_path,
                output_format=VideoFormat[settings.format.upper()],
                start=start_time_ms,
                end=end_time_ms,
                resolution=settings.resolution,
                subtitle_style=style,
                crop=settings.crop,
                boomerang=settings.boomerang,
                hd_gif=settings.colour
            )

            caption = Subtitle(
                    start_time_ms,
                    end_time_ms,
                    [line for line in settings.caption.split('\n')]
                ) if settings.caption else None

            err, ok = generate(clip_settings, subs, caption)

            if ok:
                return output_path, None
            return None, err
        except Exception as e:
            logger.exception("Failed to generate clip")
            return None, e