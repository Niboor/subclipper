import logging
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import os
import time
from contextlib import contextmanager

from .models import Video, Subtitle, ClipSettings
from subs.subs import (extract_subs, generate_video)

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
    def __init__(self, search_path: Path, font_path: Path):
        self.search_path = search_path
        self.font_path = font_path
        self._videos: List[Video] = []
        logger.info(f"Initialized VideoProcessor with search_path: {search_path}, font_path: {font_path}")

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
                ssa_events, ok = extract_subs(str(video_path))
                if ok:
                    return [
                        Subtitle(
                            id=idx,
                            start=event.start / 1000,  # Convert to seconds
                            end=event.end / 1000,
                            text=event.text,
                            video_id=video_id
                        )
                        for idx, event in enumerate(ssa_events)
                    ]
                raise Exception(ssa_events)
        except Exception as e:
            logger.exception(f"Failed to extract subtitles from {video_path}")
            raise

    def generate_clip(self, settings: ClipSettings) -> Tuple[Optional[Path], Optional[str]]:
        """Generate a video clip with the given settings."""
        try:
            with log_time("clip_generation"):
                logger.debug(f"Starting clip generation with settings: {settings}")
                errors = settings.validate()
                if errors:
                    return None, str(errors)

                try:
                    video = self._videos[settings.episode_id]
                except IndexError:
                    return None, "Invalid episode ID"

                # Create a temporary directory that won't be automatically cleaned up
                tmp_dir = Path(tempfile.mkdtemp())
                output_clip = tmp_dir / 'clip.mp4'
                output_path = tmp_dir / f'clip.{settings.format}'

                err, ok = generate_video(
                    settings.start_time,
                    settings.end_time,
                    str(output_clip),
                    str(output_path),
                    settings.text,
                    settings.caption,
                    str(video.path),
                    20,  # fps
                    settings.crop,
                    settings.boomerang,
                    settings.resolution,
                    self.font_path,
                    settings.font_size,
                    settings.colour,
                    settings.format
                )

                if ok:
                    return output_path, None
                raise Exception(err)
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
                        if query is None or query.lower() in sub.text.lower():
                            results.append(sub)

                return results
        except Exception as e:
            logger.exception("Failed to search subtitles")
            raise