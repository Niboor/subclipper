import logging
from pathlib import Path
from typing import List, Tuple, Optional
import tempfile
import os
import time
from contextlib import contextmanager

from .models import Tree, Video, Subtitle, ClipSettings
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
        logger.info(f"Initialized VideoProcessor with search_path: {search_path}, font_path: {font_path}")

    def get_tree(self, search_subpath: str) -> Tree[str]:
        subpath = self.search_path.joinpath(search_subpath)
        def convert_tree_rec(file: Path) -> Tree[str]:
            return Tree(
                value=file.relative_to(self.search_path).__str__(),
                children=[] if file.is_file() else [convert_tree_rec(child) for child in file.iterdir()]
            )
        return convert_tree_rec(subpath)

    def search_subtitles(self, search_subpath: str, search_string: str) -> List[Subtitle]:
        subpath = self.search_path.joinpath(search_subpath)
        def extract_subs_rec(file: Path) -> List[Subtitle]:
            if file.is_file():
                try:
                    subs = self._extract_subtitles(file)
                    return [sub for sub in subs if search_string in sub.text]
                except Exception as e:
                    logger.error(f"Failed to process subtitles of video {file.as_uri()}: {e}")
                    return []
            else:
                return [sub for subs in [extract_subs_rec(f) for f in file.iterdir()] for sub in subs]
        return extract_subs_rec(subpath)

    def find_subtitle(self, video_id: str, subtitle_id: int) -> Optional[Subtitle]:
        subs = self._extract_subtitles(self.search_path.joinpath(video_id))
        sub = [sub for sub in subs if sub.id == subtitle_id]
        if len(sub) > 0:
            return sub[0]
        else:
            return None

    def _extract_subtitles(self, video_path: Path) -> List[Subtitle]:
        """Extract subtitles from a video file."""
        try:
            with log_time(f"subtitle_extraction_{video_path.as_uri()}"):
                logger.debug(f"Extracting subtitles from {video_path}")
                ssa_events, ok = extract_subs(str(video_path))
                if ok:
                    return [
                        Subtitle(
                            id=idx,
                            start=event.start / 1000,  # Convert to seconds
                            end=event.end / 1000,
                            text=event.text,
                            video_id=video_path.as_uri()
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
                    settings.video_id,
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
                return None, err
        except Exception as e:
            logger.exception("Failed to generate clip")
            raise