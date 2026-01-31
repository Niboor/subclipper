from pathlib import Path
from typing import List
import pytest
import os

from src.core.models import Video, Subtitle, ClipSettings, VideoScanStatus
from src.core.subtitle_indexer import SubtitleIndexer
from src.utils.id_encoding import encode_id

samples_dir = Path(__file__).parent.parent / "samples"

@pytest.fixture(scope="session")
def subtitle_indexer():
    indexer = SubtitleIndexer(samples_dir, "test.db")
    for (path, progress) in indexer.on_scanning_progress():
        if path == Path(".") and progress == 1.0:
            yield indexer
            break
    Path.unlink(Path("test.db"))
    Path.unlink(Path("test.db.wal"))
    indexer.stop()

# Subtitle scanning is done in subtitle_indexer fixture but it should not be allowed to go indefinitely
@pytest.mark.timeout(5)
def test_all_videos_scanned(subtitle_indexer):
    sample_videos: List[str] = []
    for root, _, f in os.walk(samples_dir):
        current_dir = Path(root).relative_to(samples_dir)
        for file in f:
            sample_videos.append(current_dir.joinpath(file).__str__())

    for video_id in sample_videos:
        video = subtitle_indexer.get_video(video_id)
        assert video is not None
        assert video.status == VideoScanStatus.SCANNED_SUCCESS

@pytest.mark.timeout(5)
def test_not_get_nonexistant_video(subtitle_indexer):
    video = subtitle_indexer.get_video(samples_dir.joinpath("doesnotexist").__str__())
    assert video is None

@pytest.mark.timeout(5)
def test_find_subtitle(subtitle_indexer):
    subtitle_id = encode_id(f"sample.mp4/0")
    subtitle = subtitle_indexer.find_subtitle(subtitle_id)
    assert subtitle is not None
    assert subtitle.text == "Initializing test sequence alpha."

@pytest.mark.timeout(5)
def test_search_subtitles_from_root(subtitle_indexer):
    
    for path in [".", "subfolder"]:
        subtitles = subtitle_indexer.search_subtitles(".", "initializing")
        print(subtitles)
        assert len(subtitles) > 0
        assert len([subtitle for subtitle in subtitles if subtitle.text == "Initializing test sequence alpha."]) > 0