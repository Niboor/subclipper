import logging
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import os
import time
from contextlib import contextmanager
from ..utils.id_encoding import encode_id

from .models import Video, Subtitle, ClipSettings
from sub2clip.sub2clip import generate
from sub2clip.generation import (ClipSettings as SubSettings, TextStyle, VideoFormat)
from sub2clip.subtitles import (Subtitle as SSubtitle)

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, search_path: Path, thumbnail_path: Path, font_name: str, languages: list[str]):
        self.search_path = search_path
        self.thumbnail_path = thumbnail_path
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
            output_path = tmp_dir / f'clip.{settings.format}'

            style = TextStyle(font=self.font_name, font_size=settings.font_size)

            start_time_ms = int(settings.start_time * 1000)
            end_time_ms = int(settings.end_time * 1000)
            clip_settings = SubSettings(
                input_path=self.search_path.joinpath(settings.video_id),
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
                    start=start_time_ms,
                    end=end_time_ms,
                    text=settings.caption,
                ) if settings.caption else None

            err, ok = generate(
                clip_settings=clip_settings,
                subtitles=subs,
                caption=caption
            )

            if ok:
                return output_path, None
            return None, err
        except Exception as e:
            logger.exception("Failed to generate clip")
            return None, e
        
    def get_thumbnail(self, subtitle: Subtitle, resolution: int=50) -> Tuple[Optional[Path], Optional[str]]:
        """Get the thumbnail for the given subtitle at the set resolution"""

        filename = f"thumbnail-{encode_id(subtitle.id).replace(".", "-")}-{resolution}.jpg"
        output_path = self.thumbnail_path / filename

        if output_path.exists():
            return output_path, None
        else:
            return self._generate_thumbnail(subtitle.video_id, subtitle.start, output_path, resolution=resolution)
        
    def _generate_thumbnail(self, video_id: str, timestamp: int, output_path: Path, resolution: int=50) -> Tuple[Optional[Path], Optional[str]]:
        """Generate the stillframe for the given timestamp"""
    
        clip_settings = SubSettings(
            input_path=self.search_path.joinpath(video_id),
            output_path=output_path,
            output_format=VideoFormat.JPG,
            start=timestamp,
            end=timestamp,
            resolution=resolution
        )

        err, ok = generate(clip_settings, subtitles=[], thumbnail=True)
        if ok:
            return output_path, None
        return None, err