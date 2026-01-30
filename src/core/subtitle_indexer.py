import logging
from pathlib import Path
import threading
from typing import Any, Generator, List, Optional
from threading import Thread, Lock
from queue import Queue
from ..utils.id_encoding import encode_id
import time
import os
import duckdb
import pykka

from subs.subs import (extract_subs)

from .models import Video, VideoScanStatus, Subtitle

logger = logging.getLogger(__name__)

    

class SubtitleDatabase(pykka.ThreadingActor):
    def __init__(self, db_path: str):
        super().__init__()

        self.db_path = db_path
        self.conn: duckdb.DuckDBPyConnection

    def on_start(self) -> None:
        self.conn = duckdb.connect(self.db_path)

        cursor = self.conn.cursor()


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT NOT NULL PRIMARY KEY,
                status TEXT CHECK( status IN ('UNSCANNED', 'SCANNING', 'SCANNED_SUCCESS', 'SCANNED_FAIL') ) NOT NULL,
                fail_reason TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subtitles (
                subtitle_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                text TEXT NOT NULL,
                start_seconds REAL NOT NULL,
                end_seconds REAL NOT NULL,
                FOREIGN KEY(video_id) REFERENCES videos(video_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_queue (
                path TEXT PRIMARY KEY
            )
        ''')

        cursor.close()

        self.conn.commit()

        return super().on_start()
    
    def on_stop(self) -> None:

        self.conn.close()

        return super().on_stop()
    
    def search_subtitles(self, search_subpath: str, search_string: str) -> List[Subtitle]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subtitles WHERE video_id LIKE ? AND text LIKE ?", [f"{search_subpath if search_subpath != '.' else ''}%", f"%{search_string}%"])
        rows = cursor.fetchall()
        subs = [Subtitle(id=subtitle_id, video_id=video_id, text=text, start=start, end=end) for (subtitle_id, video_id, text, start, end) in rows]
        cursor.close()
        return subs
    
    def find_subtitle(self, subtitle_id: str) -> Optional[Subtitle]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subtitles WHERE subtitle_id = ?", [subtitle_id])
        try:
            row = cursor.fetchone()
            if row is not None:
                (subtitle_id, video_id, text, start, end) = row
                return Subtitle(
                    id=subtitle_id,
                    video_id=video_id,
                    text=text,
                    start=start,
                    end=end,
                )
            else:
                return None
        except Exception as e:
            logger.exception(e)
            return None
        finally:
            cursor.close()

    def get_video(self, video_id: str) -> Optional[Video]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id = ?", [video_id])
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        else:
            (video_id, status, fail_reason) = row
            return Video(video_id, VideoScanStatus(status), fail_reason)
        
    def get_videos(self, video_id_prefix: str) -> List[Video]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id LIKE ?", [f"{video_id_prefix if video_id_prefix.__str__() != '.' else ''}%"])
        videos = [Video(video_id, VideoScanStatus(status), fail_reason) for (video_id, status, fail_reason) in cursor.fetchall()]
        cursor.close()
        return videos
    
    def update_video(self, video: Video):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO videos (video_id, status, fail_reason) VALUES (?, ?, ?)", [video.id, video.status.value, video.fail_reason])
        self.conn.commit()
        cursor.close()

    
    def insert_subtitle(self, subtitle: Subtitle):
        cursor = self.conn.cursor()
        cursor.execute('''INSERT OR REPLACE INTO subtitles (subtitle_id, video_id, text, start_seconds, end_seconds) VALUES (?,?,?,?,?)''', [subtitle.id, subtitle.video_id, subtitle.text, subtitle.start, subtitle.end])
        self.conn.commit()
        cursor.close()


class SubtitleScanner(pykka.ThreadingActor):
    def __init__(self, root_path: Path, scan_path: Path, db: pykka.ActorProxy[SubtitleDatabase], progress_listener: Queue[tuple[Path, float]], video_update_listener: Queue[Video]):
        super().__init__()

        self.root_path = root_path
        self.scan_path = scan_path
        self.db = db

        self._progress_listener = progress_listener
        self._video_update_listener = video_update_listener

    def on_start(self) -> None:
        full_path = self.root_path.joinpath(self.scan_path)
        logger.info(f"Started the scanning of all subtitles in {full_path.__str__()}")
        files: List[tuple[Path, bool]] = []
        for root, dirs, f in os.walk(full_path):
            for file in f:
                filepath = Path(root).joinpath(file)
                logger.info(f"Checking scan status of {filepath}")
                video_id = filepath.relative_to(self.root_path).__str__()
                video: Optional[Video] = self.db.get_video(video_id).get()
                if video is None:
                    self._update_video_status(video_id, VideoScanStatus.UNSCANNED)
                    files.append((filepath, False))
                else:
                    already_scanned = video.status == 'SCANNED_SUCCESS' or video.status == 'SCANNED_FAIL'
                    files.append((filepath, already_scanned))
        scanned_files = [(file, scanned) for (file, scanned) in files if scanned]
        logger.info(f"Found {len(files)} files, {len(scanned_files)} already scanned")
        for i, (file, already_scanned) in enumerate(files):
            video_id = file.relative_to(self.root_path).__str__()
            try:
                if already_scanned:
                    logger.info(f"{i+1}/{len(files)}: Skipping file {file} as it is already present in the cache")
                else:
                    logger.info(f"{i+1}/{len(files)}: Scanning file {file}")
                    self._update_video_status(video_id, VideoScanStatus.SCANNING)
                    subtitles = self._extract_subtitles(file)
                    for subtitle in subtitles:
                        self._insert_subtitle(subtitle)
                    self._update_video_status(video_id, VideoScanStatus.SCANNED_SUCCESS)
            except Exception as e:
                logger.exception(e)
                self._update_video_status(video_id, VideoScanStatus.SCANNED_FAIL, e.__str__())
            finally:
                self.progress = (i+1) / len(files)
        logger.info("Scan complete")

    def _update_video_status(self, video_id: str, status: VideoScanStatus, fail_reason: str | None = None):
        logger.info(f"updating video status of {video_id} to {status} (errors: {fail_reason})")

        video = Video(video_id, status, fail_reason)

        self.db.update_video(video)
        self._video_update_listener.put(video)

        video_path = Path(video_id)
        segments = video_path.parts
        for i, _ in enumerate(segments[:-1]):
            partial_path = Path(*segments[0:i+1])
            percent = self._get_progress(partial_path)
            self._progress_listener.put((partial_path, percent))

    def _extract_subtitles(self, video_path: Path) -> List[Subtitle]:
        """Extract subtitles from a video file."""
        video_id = video_path.relative_to(self.root_path).__str__()
        try:
            logger.debug(f"Extracting subtitles from {video_id}")
            ssa_events, ok = extract_subs(str(video_path))
            if ok:
                return [
                    Subtitle(
                        id=encode_id(f"{video_id}/{idx}"),
                        start=event.start / 1000,  # Convert to seconds
                        end=event.end / 1000,
                        text=event.text,
                        video_id=video_id
                    )
                    for idx, event in enumerate(ssa_events) if not isinstance(event, str)
                ]
            raise Exception(ssa_events)
        except Exception as e:
            logger.exception(f"Failed to extract subtitles from {video_path}")
            raise

    def _get_progress(self, path: Path) -> float:
        videos: List[Video] = self.db.get_videos(path).get()
        scanned_videos = [video for video in videos if video.status == VideoScanStatus.SCANNED_SUCCESS or video.status == VideoScanStatus.SCANNED_FAIL]
        percent = len(scanned_videos) / len(videos) if len(videos) != 0 else 0
        return percent
    
    def _insert_subtitle(self, subtitle: Subtitle):
        self.db.insert_subtitle(subtitle)

class SubtitleIndexer():
    def __init__(self, root_path: Path, db_path: str):
        self.root_path = root_path
        self.db: pykka.ActorProxy[SubtitleDatabase] = SubtitleDatabase.start(db_path).proxy()

        self.progress_listener: Queue[tuple[Path, float]] = Queue()
        self.video_update_listener: Queue[Video] = Queue()

        SubtitleScanner.start(self.root_path, Path("."), self.db, self.progress_listener, self.video_update_listener)

    def get_scanning_progress(self, search_subpath: Path) -> Optional[float]:
        videos: List[Video] = self.db.get_videos(search_subpath).get()
        scanned_videos = [video for video in videos if video.status == VideoScanStatus.SCANNED_SUCCESS or video.status == VideoScanStatus.SCANNED_FAIL]
        percent = len(scanned_videos) / len(videos) if len(videos) != 0 else 0
        return percent

    def get_video(self, video_id: str) -> Optional[Video]:
        return self.db.get_video(video_id).get()

    def on_scanning_progress(self) -> Generator[tuple[Path, float], Any, Any]:
        while True:
            yield self.progress_listener.get()

    def on_videos_status_update(self) -> Generator[Video, Any, Any]:
        while True:
            yield self.video_update_listener.get()

    def get_path(self, search_subpath: str) -> Path:
        subpath = self.root_path.joinpath(search_subpath)
        return subpath

    def search_subtitles(self, search_subpath: str, search_string: str) -> List[Subtitle]:
        return self.db.search_subtitles(search_subpath, search_string).get()

    def find_subtitle(self, subtitle_id: str) -> Optional[Subtitle]:
        return self.db.find_subtitle(subtitle_id).get()
        
    def scan(self, path: Path):
        raise Exception("not implemented")