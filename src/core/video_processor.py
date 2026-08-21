import logging
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import os
import time
from contextlib import contextmanager
from ..utils.id_encoding import encode_id
from ..utils.metrics import timed
from ..utils.ffmpeg_concurrency import limit_ffmpeg_concurrency
from returns.result import Result, Success, Failure

from .subtitle_indexer import SubtitleIndexer
from .models import Video, Subtitle, ClipSettings
from sub2clip.sub2clip import (generate, create_thumbnail)
from sub2clip.generation import (ClipSettings as SubSettings, TextStyle, VideoFormat)
from sub2clip.subtitles import (Subtitle as SSubtitle)

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, search_path: Path, thumbnail_path: Path, font_name: str, languages: list[str], subtitle_indexer: SubtitleIndexer):
        self.search_path = search_path
        self.thumbnail_path = thumbnail_path
        self.font_name = font_name
        self.languages = languages
        self.subtitle_indexer = subtitle_indexer
        logger.info(f"Initialized VideoProcessor with search_path: {search_path}, font_name: {font_name}, language filter: {languages}")

    def _resolve_within_search_path(self, video_id: str) -> Optional[Path]:
        """Resolve video_id against search_path and verify it doesn't escape it.

        This is defense in depth on top of the caller-side check that video_id
        refers to a video the indexer actually knows about — it protects against
        any other path that ends up here without going through that check.
        """
        resolved_search_path = self.search_path.resolve()
        candidate = (self.search_path / video_id).resolve()
        if candidate != resolved_search_path and resolved_search_path not in candidate.parents:
            return None
        return candidate

    @timed("video_processor:generate_clip")
    def generate_clip(self, settings: ClipSettings, subs: list[Subtitle]) -> Result[Path, str]:
        """Generate a video clip with the given settings."""
        try:
            logger.debug(f"Starting clip generation with settings: {settings}")
            start_ts = time.time()
            errors = settings.validate()
            if errors:
                return Failure(str(errors))

            input_path = self._resolve_within_search_path(settings.video_id)
            if input_path is None:
                return Failure(f"video id {settings.video_id} is not a valid video")

            # Create a temporary directory that won't be automatically cleaned up
            tmp_dir = Path(tempfile.mkdtemp())
            output_path = tmp_dir / f'clip.{settings.format}'

            style = TextStyle(font=self.font_name, font_size=settings.font_size)

            start_time_ms = int(settings.start_time * 1000)
            end_time_ms = int(settings.end_time * 1000)
            clip_settings = SubSettings(
                input_path=input_path,
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

            ssubs = [sub.to_subtitle() for sub in subs]

            with limit_ffmpeg_concurrency():
                err = generate(
                    clip_settings=clip_settings,
                    subtitles=ssubs,
                    caption=caption
                )
            match err:
                case Failure(err):
                    return Failure(err)
            duration = time.time() - start_ts
            logger.info(f"Clip generation completed in {duration:.2f}s for video {settings.video_id}")
            return Success(output_path)
        except Exception as e:
            logger.exception("Failed to generate clip")
            return Failure(e.__str__())

    def thumbnail_path_for(self, subtitle_id: str, resolution: int=50) -> Path:
        """The on-disk cache path for a subtitle's thumbnail. Derived purely from the
        subtitle id and resolution, so callers can check the cache without a DB lookup."""
        filename = f"thumbnail-{encode_id(subtitle_id).replace('.', '-')}-{resolution}.webp"
        return self.thumbnail_path / filename

    @timed("video_processor:get_thumbnail")
    def get_thumbnail(self, subtitle: Subtitle, resolution: int=50) -> Result[Path, str]:
        """Get the thumbnail for the given subtitle at the set resolution"""

        output_path = self.thumbnail_path_for(subtitle.id, resolution)

        if output_path.exists():
            return Success(output_path)
        else:
            return self._generate_thumbnail(subtitle.video_id, subtitle.start, output_path, resolution=resolution)

    def _generate_thumbnail(self, video_id: str, timestamp: int, output_path: Path, resolution: int=50) -> Result[Path, str]:
        """Generate the stillframe for the given timestamp"""
        video = self.subtitle_indexer.get_video(video_id)
        if video is None:
            return Failure(f"video id {video_id} is not a valid video")

        input_path = self._resolve_within_search_path(video_id)
        if input_path is None:
            return Failure(f"video id {video_id} is not a valid video")

        width, height = video.width, video.height
        scaled_height = resolution
        scaled_width  = 2 * round((width * scaled_height / height) / 2)

        with limit_ffmpeg_concurrency():
            result = create_thumbnail(
                input_path,
                output_path,
                start_s=timestamp/1000.0,
                width=scaled_width,
                height=scaled_height
            )
        match result:
            case Failure(e):
                return Failure(e)
            case _:
                return Success(output_path)