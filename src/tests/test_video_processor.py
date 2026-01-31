import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import platform
from src.core.video_processor import VideoProcessor
from src.core.models import Video, Subtitle, ClipSettings, VideoScanStatus
from src.utils.id_encoding import encode_id

def get_system_font():
    """Get the system default font path based on the operating system."""
    if platform.system() == "Linux":
        return Path("/usr/share/fonts/TTF/DejaVuSans.ttf")
    elif platform.system() == "Darwin":  # macOS
        return Path("/System/Library/Fonts/Helvetica.ttc")
    elif platform.system() == "Windows":
        return Path("C:/Windows/Fonts/arial.ttf")
    else:
        raise NotImplementedError(f"Unsupported operating system: {platform.system()}")

@pytest.fixture
def sample_video_path():
    return Path(__file__).parent.parent / "samples" / "sample.mp4"

@pytest.fixture
def system_font_path():
    return get_system_font()

@pytest.fixture
def video_processor(sample_video_path, system_font_path):
    return VideoProcessor(sample_video_path.parent, system_font_path)

def test_generate_clip(video_processor, system_font_path, sample_video_path):
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
        text="Test",
        crop=False,
        resolution=500,
        subtitle_id=encode_id(f"{video.id}/0"),
        video_id=video.id,
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp",
        font_path=system_font_path
    )
    
    with patch('src.core.video_processor.generate_video') as mock_generate_video:
        mock_generate_video.return_value = (None, True)
        output_path, error = video_processor.generate_clip(settings)
        assert error is None
        assert output_path is not None
        
    # Test with invalid settings
    settings.video_id = "nonexistant"
    output_path, error = video_processor.generate_clip(settings)
    assert error is not None
    assert output_path is None

def test_generate_clip_error_handling(video_processor, system_font_path, sample_video_path):
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
        text="Test",
        crop=False,
        resolution=500,
        subtitle_id=encode_id(f"{video.id}/0"),
        video_id=video.id,
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp",
        font_path=system_font_path
    )
    
    with patch('src.core.video_processor.generate_video') as mock_generate_video:
        mock_generate_video.return_value = ("Error generating video", False)
        output_path, error = video_processor.generate_clip(settings)
        assert error == "Error generating video"
        assert output_path is None 