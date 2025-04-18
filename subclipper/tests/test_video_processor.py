import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import platform
from subclipper.core.video_processor import VideoProcessor
from subclipper.core.models import Video, Subtitle, ClipSettings

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

def test_load_videos(video_processor, sample_video_path):
    with patch('pathlib.Path.glob') as mock_glob:
        mock_glob.return_value = [sample_video_path]
        
        videos = video_processor.load_videos()
        
        assert len(videos) == 1
        video = videos[0]
        assert video.id == 0
        assert video.title == "sample"
        assert video.path == sample_video_path
        assert len(video.subs) == 5  # Check for exactly 5 subtitles

def test_search_subtitles(video_processor, sample_video_path):
    # Create test data
    video = Video(
        id=0,
        title="sample",
        path=sample_video_path,
        subs=[
            Subtitle(id=0, start=0, end=1, text="Hello world", video_id=0),
            Subtitle(id=1, start=1, end=2, text="Goodbye world", video_id=0)
        ]
    )
    video_processor._videos = [video]
    
    # Test search with query
    results = video_processor.search_subtitles("hello")
    assert len(results) == 1
    assert results[0].text == "Hello world"
    
    # Test search with video_id
    results = video_processor.search_subtitles("world", video_id=0)
    assert len(results) == 2
    
    # Test search with no matches
    results = video_processor.search_subtitles("nonexistent")
    assert len(results) == 0

def test_generate_clip(video_processor, system_font_path, sample_video_path):
    # Create test data
    video = Video(
        id=0,
        title="sample",
        path=sample_video_path,
        subs=[]
    )
    video_processor._videos = [video]
    
    # Create valid settings
    settings = ClipSettings(
        start_time=0.0,
        end_time=5.0,
        text="Test",
        crop=False,
        resolution=500,
        episode_id=0,
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp",
        font_path=system_font_path
    )
    
    with patch('subclipper.core.video_processor.generate_video') as mock_generate_video:
        mock_generate_video.return_value = (None, True)
        output_path, error = video_processor.generate_clip(settings)
        assert error is None
        assert output_path is not None
        
    # Test with invalid settings
    settings.episode_id = 999
    output_path, error = video_processor.generate_clip(settings)
    assert error is not None
    assert output_path is None

def test_generate_clip_error_handling(video_processor, system_font_path, sample_video_path):
    # Create test data
    video = Video(
        id=0,
        title="sample",
        path=sample_video_path,
        subs=[]
    )
    video_processor._videos = [video]
    
    settings = ClipSettings(
        start_time=0.0,
        end_time=5.0,
        text="Test",
        crop=False,
        resolution=500,
        episode_id=0,
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp",
        font_path=system_font_path
    )
    
    with patch('subclipper.core.video_processor.generate_video') as mock_generate_video:
        mock_generate_video.return_value = ("Error generating video", False)
        output_path, error = video_processor.generate_clip(settings)
        assert error == "Error generating video"
        assert output_path is None 