import logging
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import os
import time
from contextlib import contextmanager

from .models import Video, Subtitle, ClipSettings
from sub2clip.sub2clip import (extract_subs_by_language, generate)
from sub2clip.generation import (ClipSettings as SubSettings, TextStyle, VideoFormat)
from sub2clip.subtitles import (Subtitle as Huts)

logger = logging.getLogger(__name__)

@contextmanager
def log_time(operation: str):
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        logger.info(f"{operation} completed in {duration:.2f} seconds")

class VideoProcessor:
    def __init__(self, search_path: Path, font_name: str):
        self.search_path = search_path
        self.font_name = font_name
        self._videos: List[Video] = []
        logger.info(f"Initialized VideoProcessor with search_path: {search_path}, font_name: {font_name}")

    def load_videos(self) -> List[Video]:
        """Load all videos and their subtitles from the search path."""
        try:
            if self._videos:
                logger.debug("Videos already loaded, returning cached list")
                return self._videos

            logger.info(f"Loading videos from {self.search_path}")
            with log_time("video_loading"):
                videos = []
                for idx, video_file in enumerate(sorted(self.search_path.glob('*'))):
                    if not video_file.is_file():
                        continue

                    try:
                        subs = self._extract_subtitles(video_file, idx)
                        video = Video(
                            id=idx,
                            title=video_file.stem,
                            path=video_file,
                            subs=subs
                        )
                        videos.append(video)
                    except Exception as e:
                        logger.error(f"Failed to process video {video_file}: {e}")

                self._videos = videos
                return videos
        except Exception as e:
            logger.exception("Failed to load videos")
            raise

    def _extract_subtitles(self, video_path: Path, video_id: int) -> List[Subtitle]:
        """Extract subtitles from a video file."""
        try:
            with log_time(f"subtitle_extraction_{video_id}"):
                logger.debug(f"Extracting subtitles from {video_path}")
                subtitles, ok = extract_subs_by_language(video_path, ['eng', 'nld', 'dut', 'nl'])
                if ok:
                    return [
                        Subtitle.from_subtitle(
                            sub,
                            id=idx,
                            video_id=video_id
                        )
                        for idx, sub in enumerate(subtitles)
                    ]
                raise Exception(subtitles)
        except Exception as e:
            logger.exception(f"Failed to extract subtitles from {video_path}")
            raise

    def generate_clip(self, settings: ClipSettings, subs: list[Huts]) -> Tuple[Optional[Path], Optional[str]]:
        """Generate a video clip with the given settings."""
        try:
            with log_time("clip_generation"):
                logger.debug(f"Starting clip generation with settings: {settings}")
                errors = settings.validate()
                if errors:
                    return None, str(errors)

                try:
                    video = self._videos[settings.episode]
                except IndexError:
                    return None, "Invalid episode ID"

                # Create a temporary directory that won't be automatically cleaned up
                tmp_dir = Path(tempfile.mkdtemp())
                output_clip = tmp_dir / 'clip.mp4'
                output_path = tmp_dir / f'clip.{settings.format}'

                style = TextStyle(font="Google Sans", font_size=settings.font_size)

                clip_settings = SubSettings(
                    input_path=video.path,
                    clip_path=output_clip,
                    output_path=output_path,
                    output_format=VideoFormat[settings.format.upper()],
                    start=settings.start_time * 1000,
                    end=settings.end_time * 1000,
                    resolution=settings.resolution,
                    subtitle_style=style,
                    crop=settings.crop,
                    boomerang=settings.boomerang
                )

                err, ok = generate(clip_settings, subs)

                if ok:
                    return output_path, None
                return None, err
        except Exception as e:
            logger.exception("Failed to generate clip")
            raise

    def search_subtitles(self, query: Optional[str], video_id: Optional[int] = None) -> List[Subtitle]:
        """Search subtitles across all videos or a specific video."""
        try:
            with log_time("subtitle_search"):
                logger.debug(f"Searching subtitles with query: {query}, video_id: {video_id}")
                videos = self.load_videos()
                results = []

                for video in videos:
                    if video_id is not None and video.id != video_id:
                        continue

                    for sub in video.subs:
                        if query is None or any(query.lower() in line.lower() for line in sub.text):
                            results.append(sub)

                return results
        except Exception as e:
            logger.exception("Failed to search subtitles")
            raise