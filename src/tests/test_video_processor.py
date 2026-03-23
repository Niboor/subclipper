import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.core.video_processor import VideoProcessor
from src.core.models import Video, Subtitle, ClipSettings, VideoScanStatus
from src.utils.id_encoding import encode_id
from sub2clip.subtitles import Subtitle as SSubtitle
from returns.pipeline import is_successful
from returns.result import Success, Failure
import tempfile

@pytest.fixture
def sample_video_path():
    return Path(__file__).parent.parent / "samples" / "sample.mp4"

@pytest.fixture
def video_processor(sample_video_path: Path):
    tmp_thumbnail_dir = Path(tempfile.mkdtemp())
    return VideoProcessor(sample_video_path.parent, tmp_thumbnail_dir, "Arial", [])

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
        mock_generate_clip.return_value = Success(Path())
        output_path = video_processor.generate_clip(settings, [])
        assert is_successful(output_path)

    # Test with invalid settings
    settings.video_id = "nonexistant"
    output_path = video_processor.generate_clip(settings, [])
    assert not is_successful(output_path)

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
        mock_generate_clip.return_value = Failure("Error generating video")
        output_path = video_processor.generate_clip(settings, [])
        assert not is_successful(output_path)
        assert output_path.failure() == "Error generating video"