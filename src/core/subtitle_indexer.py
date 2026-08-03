import logging
from pathlib import Path
from typing import Any, Generator, List, Optional
from queue import Queue
from ..utils.id_encoding import encode_id
import os
import time
import duckdb
import pykka
import math
import hashlib

from sub2clip.sub2clip import (extract_subs, extract_subs_by_language, extract_dimensions)
from .models import Video, VideoScanStatus, Subtitle
from returns.result import Result, Failure, Success

logger = logging.getLogger(__name__)

class SubtitleDatabase(pykka.ThreadingActor):
    def __init__(self, db_path: str):
        super().__init__()

        self.db_path = db_path
        self.conn: duckdb.DuckDBPyConnection

    def on_start(self) -> None:
        self.conn = duckdb.connect(self.db_path) if self.db_path != "" else duckdb.connect()

        cursor = self.conn.cursor()


        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT NOT NULL PRIMARY KEY,
                status TEXT CHECK( status IN ('UNSCANNED', 'SCANNING', 'SCANNED_SUCCESS', 'SCANNED_FAIL') ) NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                fail_reason TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subtitles (
                subtitle_id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                text TEXT NOT NULL,
                start_time BIGINT NOT NULL,
                end_time BIGINT NOT NULL,
                prv_subtitle TEXT,
                nxt_subtitle TEXT,
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

    def get_subtitle_pages(self, search_subpath: str, search_string: str, page_length: int) -> int:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM subtitles WHERE video_id LIKE ? AND text ILIKE ?", [f"{search_subpath if search_subpath != '.' else ''}%", f"%{search_string}%"])
        row = cursor.fetchone()
        count: int
        if row is None:
            count = 0
        else:
            count = row[0]
        pages = math.ceil(count / page_length)
        return pages

    def search_subtitles(self, search_subpath: str, search_string: str, page: int, page_length: int | None) -> List[Subtitle]:
        offset = page * page_length if page_length is not None else None
        cursor = self.conn.cursor()
        # Order results consistently by video_id then start_time so paging and rank calculations are stable
        cursor.execute(f"SELECT * FROM subtitles WHERE video_id LIKE ? AND text ILIKE ? ORDER BY video_id, start_time LIMIT ?{ ' OFFSET ?' if offset is not None else '' }", [f"{search_subpath if search_subpath != '.' else ''}%", f"%{search_string}%", page_length, *([offset] if offset is not None else [])])
        rows = cursor.fetchall()
        subs = [Subtitle(
                id=subtitle_id,
                video_id=video_id,
                text=text,
                start=start,
                end=end,
                prv_id=prv_id,
                nxt_id=nxt_id
            ) for (subtitle_id, video_id, text, start, end, prv_id, nxt_id) in rows
        ]
        cursor.close()
        return subs

    def get_subtitle_index(self, subtitle_id: str, search_subpath: str, search_string: str) -> Optional[int]:
        """Return the 0-based index (row number) of the given subtitle in the ordered result set
        filtered by search_subpath and search_string. Returns None if subtitle not found."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT video_id, start_time FROM subtitles WHERE subtitle_id = ?", [subtitle_id])
        row = cursor.fetchone()
        if row is None:
            cursor.close()
            return None

        video_id, start_time = row

        # Count rows that come before this subtitle using the same ORDER BY used in search_subtitles
        cursor.execute(
            "SELECT COUNT(*) FROM subtitles WHERE video_id LIKE ? AND text ILIKE ? AND (video_id < ? OR (video_id = ? AND start_time < ?))",
            [f"{search_subpath if search_subpath != '.' else ''}%", f"%{search_string}%", video_id, video_id, start_time]
        )
        count_row = cursor.fetchone()
        cursor.close()
        if count_row is None:
            return 0
        return int(count_row[0])

    def find_subtitle(self, subtitle_id: str) -> Optional[Subtitle]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subtitles WHERE subtitle_id = ?", [subtitle_id])
        try:
            row = cursor.fetchone()
            if row is not None:
                (subtitle_id, video_id, text, start, end, prv_id, nxt_id) = row
                return Subtitle(
                    id=subtitle_id,
                    video_id=video_id,
                    text=text,
                    start=start,
                    end=end,
                    prv_id=prv_id,
                    nxt_id=nxt_id
                )
            else:
                return None
        except Exception as e:
            logger.exception(e)
            return None
        finally:
            cursor.close()

    def get_video_subtitles(self, video_id: str) -> List[Subtitle]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM subtitles WHERE video_id = ?", [video_id])
        rows = cursor.fetchall()
        subs = [Subtitle(
            id=subtitle_id,
            video_id=video_id,
            text=text,
            start=start,
            end=end,
            prv_id=prv_id,
            nxt_id=nxt_id,
        ) for (subtitle_id, video_id, text, start, end, prv_id, nxt_id) in rows]
        cursor.close()
        return subs

    def get_video(self, video_id: str) -> Optional[Video]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id = ?", [video_id])
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            return None
        else:
            (video_id, status, width, height, fail_reason) = row
            return Video(video_id, VideoScanStatus(status), width, height, fail_reason)

    def get_videos(self, video_id_prefix: str) -> List[Video]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE video_id LIKE ?", [f"{video_id_prefix if video_id_prefix.__str__() != '.' else ''}%"])
        videos = [Video(video_id, VideoScanStatus(status), width, height, fail_reason) for (video_id, status, width, height, fail_reason) in cursor.fetchall()]
        cursor.close()
        return videos

    def update_video(self, video: Video):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO videos (video_id, status, width, height, fail_reason) VALUES (?, ?, ?, ?, ?)", [video.id, video.status.value, video.width, video.height, video.fail_reason])
        self.conn.commit()
        cursor.close()

    def insert_subtitles(self, subtitles: List[Subtitle]):
        cursor = self.conn.cursor()
        cursor.begin()
        for subtitle in subtitles:
            cursor.execute(
                "INSERT OR REPLACE INTO subtitles (subtitle_id, video_id, text, start_time, end_time, prv_subtitle, nxt_subtitle) VALUES (?,?,?,?,?,?,?)",
                [subtitle.id, subtitle.video_id, subtitle.text, subtitle.start, subtitle.end, subtitle.prv_id, subtitle.nxt_id])
        cursor.commit()
        self.conn.commit()
        cursor.close()


class SubtitleScanner(pykka.ThreadingActor):
    def __init__(self,
        root_path: Path,
        scan_path: Path,
        db: pykka.ActorProxy[SubtitleDatabase],
        progress_listener: Queue[tuple[Path, float]],
        video_update_listener: Queue[Video],
        languages: list[str]
    ):
        super().__init__()

        # The absolute path to the root of the file system where all the video files are stored
        self.root_path = root_path
        # The relative path within the root path where you want to scan all files in
        self.scan_path = scan_path
        self.db = db

        self._progress_listener = progress_listener
        self._video_update_listener = video_update_listener

        self.languages = languages

    def on_start(self) -> None:
        # the full absolute path to the scan path
        full_path = self.root_path.joinpath(self.scan_path)
        logger.info(f"Started the scanning of all subtitles in {full_path.__str__()}")

        videos: List[Video] = []
        for root, _, f in os.walk(full_path):
            # The directory in which the file is currently located at, relative to the root path from which all files come from
            current_dir = Path(root).relative_to(self.root_path)
            for file in f:
                video_id = current_dir.joinpath(file).__str__()
                logger.info(f"Checking scan status of {video_id}")
                video: Optional[Video] = self.db.get_video(video_id).get()
                if video is None:
                    self._update_video_status(video_id, VideoScanStatus.UNSCANNED)
                    videos.append(Video(video_id, VideoScanStatus.UNSCANNED, width=-1, height=-1, fail_reason=None))
                else:
                    videos.append(video)
        scanned_videos = [video for video in videos if video.already_scanned()]
        logger.info(f"Found {len(videos)} files, {len(scanned_videos)} already scanned")
        for i, video in enumerate(videos):
            try:
                if video.already_scanned():
                    logger.info(f"{i+1}/{len(videos)}: Skipping file {video.id} as it is already present in the cache")
                else:
                    logger.info(f"{i+1}/{len(videos)}: Scanning file {video.id}")
                    self._update_video_status(video.id, VideoScanStatus.SCANNING)
                    subtitles = self._extract_subtitles(Path(video.id))
                    self.db.insert_subtitles(subtitles)
                    width = height = None
                    match extract_dimensions(self.root_path.joinpath(Path(video.id))):
                        case Failure(e):
                            logger.error(f'Failed to extract dimensions from video {video.id}: {e}')
                            raise Exception(e)
                        case Success((width, height)):
                            pass
                    self._update_video_status(video.id, VideoScanStatus.SCANNED_SUCCESS, width=width, height=height)
            except Exception as e:
                logger.exception(e)
                self._update_video_status(video.id, VideoScanStatus.SCANNED_FAIL, fail_reason=e.__str__())
        logger.info("Scan complete")

    def _update_video_status(self, video_id: str, status: VideoScanStatus, width: int =-1, height: int =-1, fail_reason: str | None = None):
        logger.debug(f"updating video status of {video_id} to {status} (errors: {fail_reason})")

        video = Video(video_id, status, width=width, height=height, fail_reason=fail_reason)

        self.db.update_video(video)
        self._video_update_listener.put(video)

        video_path = Path(video_id)
        segments = [Path(""), *video_path.parts[:-1]]
        for i, _ in enumerate(segments):
            partial_path = Path(*segments[0:i+1])
            percent = self._get_progress(partial_path)
            self._progress_listener.put((partial_path, percent))

    def _extract_subtitles(self, video_id: Path) -> List[Subtitle]:
        """Extract subtitles from a video file."""
        absolute_video_path = self.root_path.joinpath(video_id)
        try:
            logger.debug(f"Extracting subtitles from {video_id}")
            start_ts = time.time()
            langs = [lang.strip().lower() for lang in self.languages] if self.languages else None
            subtitles = extract_subs_by_language(absolute_video_path, langs) if langs else extract_subs(absolute_video_path)
            # Significantly reduces id length of subtitle while remaining unique per video
            video_id_md5 = hashlib.md5(video_id.__str__().encode("utf-8")).hexdigest()[0:8]
            match subtitles:
                case Success(subtitles):
                    result = [
                        Subtitle.from_subtitle(
                            sub,
                            id=encode_id(f"{video_id_md5}/{idx}"),
                            prv_id=encode_id(f"{video_id_md5}/{idx-1}") if idx > 0 else '',
                            nxt_id=encode_id(f"{video_id_md5}/{idx+1}") if idx < len(subtitles)-1 else '',
                            video_id=video_id.__str__()
                        )
                        for idx, sub in enumerate(subtitles)
                    ]
                    duration = time.time() - start_ts
                    logger.info(f"Extracted {len(result)} subtitles from {video_id} in {duration:.2f}s")
                    return result
                case Failure(err):
                    raise Exception(err)
                case _:
                    raise Exception("unreachable")
        except Exception as e:
            logger.exception(f"Failed to extract subtitles from {video_id}")
            raise

    def _get_progress(self, path: Path) -> float:
        videos: List[Video] = self.db.get_videos(path).get()
        scanned_videos = [video for video in videos if video.status == VideoScanStatus.SCANNED_SUCCESS or video.status == VideoScanStatus.SCANNED_FAIL]
        percent = len(scanned_videos) / len(videos) if len(videos) != 0 else 0
        return percent

class SubtitleIndexer():
    def __init__(self, root_path: Path, db_path: str, languages: list[str]):
        self.root_path = root_path
        self._db: pykka.ActorRef[SubtitleDatabase] = SubtitleDatabase.start(db_path)
        self.db: pykka.ActorProxy[SubtitleDatabase] = self._db.proxy()

        self.progress_listener: Queue[tuple[Path, float]] = Queue()
        self.video_update_listener: Queue[Video] = Queue()

        self._subtitle_scanner = SubtitleScanner.start(self.root_path, Path("."), self.db, self.progress_listener, self.video_update_listener, languages)

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

    def get_subtitle_pages(self, search_subpath: str, search_string: str, page_length: int) -> int:
        return self.db.get_subtitle_pages(search_subpath, search_string, page_length).get()

    def search_subtitles(self, search_subpath: str, search_string: str, page: int, page_length: int | None) -> List[Subtitle]:
        return self.db.search_subtitles(search_subpath, search_string, page, page_length).get()

    def get_subtitle_index(self, subtitle_id: str, search_subpath: str, search_string: str) -> Optional[int]:
        return self.db.get_subtitle_index(subtitle_id, search_subpath, search_string).get()

    def find_subtitle(self, subtitle_id: str) -> Optional[Subtitle]:
        return self.db.find_subtitle(subtitle_id).get()

    def get_video_subtitles(self, video_id: str):
        return self.db.get_video_subtitles(video_id).get()

    def scan(self, path: Path):
        raise Exception("not implemented")

    def stop(self):
        self._db.stop()
        self._subtitle_scanner.stop()