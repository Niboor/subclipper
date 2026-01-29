import logging
from pathlib import Path
import threading
from typing import Any, Generator, List, Optional
import sqlite3
from threading import Thread, Lock
from queue import Queue
from ..utils.id_encoding import encode_id
import time
import os

from subs.subs import (extract_subs)

from .models import Video, VideoScanStatus, Subtitle

logger = logging.getLogger(__name__)

class SubtitleScanner(threading.Thread):
    def __init__(self, search_path: Path, sqlite_path: str):
        threading.Thread.__init__(self)
        self.search_path = search_path
        self.sqlite_path = sqlite_path
        self._progress_listener: Queue[tuple[Path, float]] = Queue()
        self.__video_update_listener: Queue[Video] = Queue()

        with sqlite3.connect(self.sqlite_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO scan_queue (path) VALUES (?)", [self.search_path.__str__()])
            conn.commit()

    def run(self):
        try:
            self.conn = sqlite3.connect(self.sqlite_path)
            cursor = self.conn.cursor()
            while True:
                cursor.execute("SELECT * FROM scan_queue")
                row = cursor.fetchone()
                if row is None:
                    time.sleep(1)
                    continue
                path = row[0]
                logger.info(f"Picking up scan request for path {self.search_path.joinpath(path).__str__()}")
                cursor.execute("DELETE FROM scan_queue WHERE path = ?", [path])
                self.conn.commit()
                self.scan(path)
        finally:
            if self.conn:
                self.conn.close()

    def scan(self, path: Path):
        cursor = self.conn.cursor()

        logger.info(f"Started the scanning of all subtitles in {self.search_path.joinpath(path).__str__()}")
        files: List[tuple[Path, bool]] = []
        for root, dirs, f in os.walk(path):
            for file in f:
                filepath = Path(root).joinpath(file)
                logger.info(f"Checking scan status of {filepath}")
                video_id = filepath.relative_to(self.search_path).__str__()
                cursor.execute("SELECT * FROM videos WHERE video_id = ?", [video_id])
                row = cursor.fetchone()
                if row is None:
                    self.update_video_status(video_id, VideoScanStatus.UNSCANNED)
                    files.append((filepath, False))
                else:
                    (video_id, status, fail_reason) = row
                    already_scanned = status == 'SCANNED_SUCCESS' or status == 'SCANNED_FAIL'
                    files.append((filepath, already_scanned))
        scanned_files = [(file, scanned) for (file, scanned) in files if scanned]
        logger.info(f"Found {len(files)} files, {len(scanned_files)} already scanned")
        for i, (file, already_scanned) in enumerate(files):
            video_id = file.relative_to(self.search_path).__str__()
            try:
                if already_scanned:
                    logger.info(f"{i+1}/{len(files)}: Skipping file {file} as it is already present in the cache")
                else:
                    logger.info(f"{i+1}/{len(files)}: Scanning file {file}")
                    self.update_video_status(video_id, VideoScanStatus.SCANNING)
                    subtitles = self._extract_subtitles(file)
                    for subtitle in subtitles:
                        self._insert_subtitle(subtitle)
                    self.update_video_status(video_id, VideoScanStatus.SCANNED_SUCCESS)
            except Exception as e:
                logger.exception(e)
                self.update_video_status(video_id, VideoScanStatus.SCANNED_FAIL, e.__str__())
                self.conn.commit()
            finally:
                self.progress = (i+1) / len(files)
        logger.info("Scan complete")


    def update_video_status(self, video_id: str, status: VideoScanStatus, fail_reason: str | None = None):
        cursor = self.conn.cursor()

        video = Video(video_id, status, fail_reason)

        cursor.execute("INSERT OR REPLACE INTO videos (video_id, status, fail_reason) VALUES (?, ?, ?)", [video_id, status.value, fail_reason])
        self.conn.commit()
        self.__video_update_listener.put(video)

        video_path = Path(video_id)
        segments = video_path.parts
        for i, _ in enumerate(segments[:-1]):
            partial_path = Path(*segments[0:i+1])
            percent = self.get_progress(self.conn, partial_path)
            self._progress_listener.put((partial_path, percent))
        
    
        # progress = self.get_progress()
        # self._progress_listener.put(progress)

    def get_progress(self, conn: sqlite3.Connection, path: Path) -> float:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id LIKE ?", [f"{path if path.__str__() != '.' else ''}%"])
        videos = [Video(video_id, VideoScanStatus(status), fail_reason) for (video_id, status, fail_reason) in cursor.fetchall()]
        scanned_videos = [video for video in videos if video.status == VideoScanStatus.SCANNED_SUCCESS or video.status == VideoScanStatus.SCANNED_FAIL]
        percent = len(scanned_videos) / len(videos) if len(videos) != 0 else 0
        return percent

    def on_progress(self) -> Generator[tuple[Path, float], None, None]:
        while True:
            yield self._progress_listener.get()

    def on_videos_status_update(self) -> Generator[Video, None, None]:
        while True:
            yield self.__video_update_listener.get()

    def _extract_subtitles(self, video_path: Path) -> List[Subtitle]:
        """Extract subtitles from a video file."""
        video_id = video_path.relative_to(self.search_path).__str__()
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
                    for idx, event in enumerate(ssa_events)
                ]
            raise Exception(ssa_events)
        except Exception as e:
            logger.exception(f"Failed to extract subtitles from {video_path}")
            raise

    def _insert_subtitle(self, subtitle: Subtitle):
        cursor = self.conn.cursor()
        cursor.execute('''
        INSERT INTO subtitles (subtitle_id, video_id, text, start, end)
        VALUES (?,?,?,?,?)
        ON CONFLICT(subtitle_id) DO UPDATE SET
            video_id = excluded.video_id,
            text     = excluded.text,
            start    = excluded.start,
            end      = excluded.end;
        ''', [subtitle.id, subtitle.video_id, subtitle.text, subtitle.start, subtitle.end])
        self.conn.commit()

class SubtitleIndexer:

    scanner: Optional[SubtitleScanner] = None

    def __init__(self, search_path: Path, sqlite_path: str):
        self.search_path = search_path
        self.sqlite_path = sqlite_path

        self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
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
                start REAL NOT NULL,
                end REAL NOT NULL,
                FOREIGN KEY(video_id) REFERENCES videos(video_id)
            )
        ''')
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS subtitles_fts
            USING fts5(
                text,
                content='subtitles',
                content_rowid='rowid'
            );
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS subtitles_ai AFTER INSERT ON subtitles BEGIN
                INSERT INTO subtitles_fts(rowid, text)
                VALUES (new.rowid, new.text);
            END;
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS subtitles_ad AFTER DELETE ON subtitles BEGIN
                INSERT INTO subtitles_fts(subtitles_fts, rowid, text)
                VALUES('delete', old.rowid, old.text);
            END;
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS subtitles_au AFTER UPDATE ON subtitles BEGIN
                INSERT INTO subtitles_fts(subtitles_fts, rowid, text)
                VALUES('delete', old.rowid, old.text);
                INSERT INTO subtitles_fts(rowid, text)
                VALUES (new.rowid, new.text);
            END;
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_queue (
                path TEXT PRIMARY KEY
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS subtitle_text_index ON subtitles(text COLLATE NOCASE)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS subtitles_video_id_index ON subtitles(video_id COLLATE NOCASE)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS video_id_index ON videos(video_id COLLATE NOCASE)
        ''')

        cursor.close()

        self.conn.commit()
        if SubtitleIndexer.scanner is None:
            SubtitleIndexer.scanner = SubtitleScanner(search_path, sqlite_path)
            SubtitleIndexer.scanner.start()

    def get_scanning_progress(self, search_subpath: Path) -> Optional[float]:
        while SubtitleIndexer.scanner is None:
            return None

        progress = SubtitleIndexer.scanner.get_progress(self.conn, search_subpath)
        return progress

    def get_video(self, video_id: str) -> Optional[Video]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id = ?", [video_id])
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        else:
            (id, status, fail_reason) = row
            return Video(id, VideoScanStatus(status), fail_reason)

    def on_scanning_progress(self) -> Generator[tuple[Path, float], Any, Any]:
        while SubtitleIndexer.scanner is None:
            time.sleep(1)

        for progress in SubtitleIndexer.scanner.on_progress():
            yield progress

    def on_videos_status_update(self) -> Generator[Video, Any, Any]:
        while SubtitleIndexer.scanner is None:
            time.sleep(1)
        
        for video in SubtitleIndexer.scanner.on_videos_status_update():
            yield video

    def get_path(self, search_subpath: str) -> Path:
        subpath = self.search_path.joinpath(search_subpath)
        return subpath

    def search_subtitles(self, search_subpath: str, search_string: str) -> List[Subtitle]:
        cursor = self.conn.cursor()
        if search_string == "":
            logger.warning("About to search ALL subtitles. This may crash the worker")
            cursor.execute("SELECT s.subtitle_id, s.video_id, s.text, s.start, s.end FROM subtitles_fts f JOIN subtitles s ON s.rowid = f.rowid WHERE s.video_id LIKE ?", [f"{search_subpath if search_subpath != '.' else ''}%"])
        else:
            cursor.execute("SELECT s.subtitle_id, s.video_id, s.text, s.start, s.end FROM subtitles_fts f JOIN subtitles s ON s.rowid = f.rowid WHERE s.video_id LIKE ? AND subtitles_fts MATCH ?", [f"{search_subpath if search_subpath != '.' else ''}%", search_string])
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
        finally:
            cursor.close()
        
    def scan(self, path: Path):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO scan_queue (path) VALUES (?)", [path.__str__()])
        self.conn.commit()
        cursor.close()

        if SubtitleIndexer.scanner is None:
            return
        
        SubtitleIndexer.scanner.update_video_status(path.__str__(), VideoScanStatus.UNSCANNED)