import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.core.video_processor import VideoProcessor
from src.core.models import Video, Subtitle, ClipSettings, VideoScanStatus
from src.utils.id_encoding import encode_id
from sub2clip.subtitles import Subtitle as SSubtitle

@pytest.fixture
def sample_video_path():
    return Path(__file__).parent.parent / "samples" / "sample.mp4"

@pytest.fixture
def video_processor(sample_video_path: Path):
    return VideoProcessor(sample_video_path.parent, "Arial", None)

def test_load_videos(video_processor: VideoProcessor, sample_video_path: Path):
    with patch('pathlib.Path.glob') as mock_glob:
        mock_glob.return_value = [sample_video_path]

        videos = video_processor.load_videos()

        assert len(videos) == 1
        video = videos[0]
        assert video.id == 0
        assert video.title == "sample"
        assert video.path == sample_video_path
        assert len(video.subs) == 5  # Check for exactly 5 subtitles

def test_search_subtitles(video_processor: VideoProcessor, sample_video_path: Path):
    # Create test data
    video = Video(
        id=0,
        title="sample",
        path=sample_video_path,
        subs=[
            Subtitle(id=0, start=0, end=1, text=["Hello world"], video_id=0),
            Subtitle(id=1, start=1, end=2, text=["Goodbye world"], video_id=0)
        ]
    )
    video_processor._videos = [video]

    # Test search with query
    results = video_processor.search_subtitles("hello")
    assert len(results) == 1
    assert results[0].text[0] == "Hello world"

    # Test search with video_id
    results = video_processor.search_subtitles("world", video_id=0)
    assert len(results) == 2

    # Test search with no matches
    results = video_processor.search_subtitles("nonexistent")
    assert len(results) == 0

def test_generate_clip(video_processor: VideoProcessor, sample_video_path: Path):
    # Create test data
    video = Video(
        id=(Path(__file__).parent.parent / "samples" / "sample.mp4").__str__(),
        status=VideoScanStatus.SCANNED_SUCCESS,
        fail_reason=None
    )
    video_processor._videos = [video]

    # Create valid settings
    settings = ClipSettings(
        start_time=0.0,
        end_time=5.0,
        original_start_time=0.0,
        original_end_time=5.0,
        crop=False,
        resolution=500,
        subtitle_id=encode_id(f"{video.id}/0"),
        video_id=video.id,
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp"
    )

    with patch('src.core.video_processor.VideoProcessor.generate_clip') as mock_generate_clip:
        mock_generate_clip.return_value = (Path(), None)
        output_path, error = video_processor.generate_clip(settings, [])
        assert error is None
        assert output_path is not None

    # Test with invalid settings
    settings.video_id = "nonexistant"
    output_path, error = video_processor.generate_clip(settings, [])
    assert error is not None
    assert output_path is None

def test_generate_clip_error_handling(video_processor: VideoProcessor, sample_video_path: Path):
    # Create test data
    video = Video(
        id=(Path(__file__).parent.parent / "samples" / "sample.mp4").__str__(),
        status=VideoScanStatus.SCANNED_SUCCESS,
        fail_reason=None
    )
    video_processor._videos = [video]

    settings = ClipSettings(
        start_time=0.0,
        end_time=5.0,
        original_start_time=0.0,
        original_end_time=5.0,
        crop=False,
        resolution=500,
        subtitle_id=encode_id(f"{video.id}/0"),
        video_id=video.id,
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp"
    )

    with patch('src.core.video_processor.VideoProcessor.generate_clip') as mock_generate_clip:
        mock_generate_clip.return_value = (None, "Error generating video")
        output_path, error = video_processor.generate_clip(settings, [])
        assert error == "Error generating video"
        assert output_path is None