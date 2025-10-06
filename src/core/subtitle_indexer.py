import logging
from pathlib import Path
import threading
from typing import Any, Generator, List, Optional
import sqlite3
from threading import Thread, Lock
from queue import Queue
import time
import os

from subs.subs import (extract_subs)

from .models import Video, Subtitle

logger = logging.getLogger(__name__)

class SubtitleScanner(threading.Thread):
    def __init__(self, search_path: Path, sqlite_path: str):
        threading.Thread.__init__(self)
        self.search_path = search_path
        self.sqlite_path = sqlite_path
        self._progress = None
        self._progress_listener: Queue[Optional[float]] = Queue()

    def run(self):
        logger.info(f"Started the scanning of all subtitles in {self.search_path}")
        self.conn = sqlite3.connect(self.sqlite_path)
        self.cursor = self.conn.cursor()
        files: List[tuple[Path, bool]] = []
        for root, dirs, f in os.walk(self.search_path):
            for file in f:
                filepath = Path(root).joinpath(file)
                logger.info(f"Checking scan status of {filepath}")
                self.cursor.execute("SELECT * FROM subtitles WHERE video_id = ?", [filepath.relative_to(self.search_path).__str__()])
                row = self.cursor.fetchone()
                files.append((filepath, row is not None))
        scanned_files = [(file, scanned) for (file, scanned) in files if scanned]
        logger.info(f"Found {len(files)} files, {len(scanned_files)} already scanned")
        self.progress = len(scanned_files) / len(files) if len(files) > 0 else 0
        for i, (file, already_scanned) in enumerate(files):
            try:
                if already_scanned:
                    logger.info(f"{i+1}/{len(files)}: Skipping file {file} as it is already present in the cache")
                else:
                    logger.info(f"{i+1}/{len(files)}: Scannning file {file}")
                    subtitles = self._extract_subtitles(file)
                    for subtitle in subtitles:
                        self._insert_subtitle(subtitle)
            except Exception as e:
                logger.exception(e)
            finally:
                self.progress = (i+1) / len(files)
        logger.info("Scan complete")
        self.conn.close()

    @property
    def progress(self):
        return self._progress
    
    @progress.setter
    def progress(self, new_value):
        self._progress = new_value
        self._progress_listener.put(new_value)

    def on_progress(self):
        yield self.progress
        while True:
            yield self._progress_listener.get()

    def _extract_subtitles(self, video_path: Path) -> List[Subtitle]:
        """Extract subtitles from a video file."""
        video_id = video_path.relative_to(self.search_path).__str__()
        try:
            logger.debug(f"Extracting subtitles from {video_id}")
            ssa_events, ok = extract_subs(str(video_path))
            if ok:
                return [
                    Subtitle(
                        id=f"{video_id}/{idx}".encode("utf-8").hex(),
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

    def _insert_subtitle(self, subtitle: Subtitle):
        self.cursor.execute('INSERT OR REPLACE INTO subtitles (subtitle_id, video_id, text, start, end) VALUES (?,?,?,?,?)', [subtitle.id, subtitle.video_id, subtitle.text, subtitle.start, subtitle.end])
        self.conn.commit()

class SubtitleIndexer:

    scanner: Optional[SubtitleScanner] = None

    def __init__(self, search_path: Path, sqlite_path: str):
        self.search_path = search_path
        self.sqlite_path = sqlite_path

        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subtitles (
                subtitle_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                text TEXT NOT NULL,
                start REAL NOT NULL,
                end REAL NOT NULL
            )
        ''')

        cursor.close()

        self.conn.commit()
        if SubtitleIndexer.scanner is None:
            SubtitleIndexer.scanner = SubtitleScanner(search_path, sqlite_path)
            SubtitleIndexer.scanner.start()

    def get_scanning_progress(self, search_subpath: Path) -> Generator[Optional[float], Any, Any]:
        while SubtitleIndexer.scanner is None:
            yield None
            time.sleep(1)

        for progress in SubtitleIndexer.scanner.on_progress(): # type: ignore
            yield progress

    def get_path(self, search_subpath: str) -> Path:
        subpath = self.search_path.joinpath(search_subpath)
        return subpath

    def search_subtitles(self, search_subpath: str, search_string: str) -> List[Subtitle]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subtitles WHERE video_id LIKE ? AND text LIKE ?", [f"{search_subpath if search_subpath != '.' else ''}%", f"%{search_string}%"])
        rows = cursor.fetchall()
        subs = [Subtitle(id=subtitle_id, video_id=video_id, text=text, start=start, end=end) for (subtitle_id, video_id, text, start, end) in rows]
        cursor.close()
        return subs

    def find_subtitle(self, subtitle_id: str) -> Optional[Subtitle]:
        # subtitle_id_unquoted = bytes.fromhex(subtitle_id).decode("utf-8")
        # [video_id, subtitle_idx] = subtitle_id_unquoted.rsplit('/', 1)
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subtitles WHERE subtitle_id = ?", [subtitle_id])
        try:
            (subtitle_id, video_id, text, start, end) = cursor.fetchone()
            return Subtitle(
                id=subtitle_id,
                video_id=video_id,
                text=text,
                start=start,
                end=end,
            )
        except Exception as e:
            logger.exception(e)
            return None