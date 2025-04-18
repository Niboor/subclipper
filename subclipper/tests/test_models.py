import pytest
from pathlib import Path
from subclipper.core.models import Video, Subtitle, ClipSettings

def test_video_creation():
    video = Video(
        id=1,
        title="test_video",
        path=Path("/path/to/video.mp4"),
        subs=[]
    )
    assert video.id == 1
    assert video.title == "test_video"
    assert video.path == Path("/path/to/video.mp4")
    assert video.subs == []

def test_subtitle_creation():
    sub = Subtitle(
        id=1,
        start=10.0,
        end=15.0,
        text="Test subtitle",
        video_id=1
    )
    assert sub.id == 1
    assert sub.start == 10.0
    assert sub.end == 15.0
    assert sub.text == "Test subtitle"
    assert sub.video_id == 1

def test_clip_settings_validation():
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
        font_path=Path("/path/to/font.ttf")
    )
    assert settings.validate() == {}

def test_clip_settings_validation_errors():
    # Test end time before start time
    settings = ClipSettings(
        start_time=5.0,
        end_time=0.0,
        text="Test",
        crop=False,
        resolution=500,
        episode_id=0,
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp",
        font_path=Path("/path/to/font.ttf")
    )
    assert "end" in settings.validate()

    # Test clip too long
    settings.end_time = 16.0  # 16.0 - 5.0 = 11.0 seconds, which is too long
    assert "end" in settings.validate()

    # Test invalid resolution
    settings.end_time = 5.0
    settings.resolution = 10
    assert "resolution" in settings.validate()

    # Test invalid episode ID
    settings.resolution = 500
    settings.episode_id = -1
    assert "episode" in settings.validate()

    # Test text too long
    settings.episode_id = 0
    settings.text = "a" * 201
    assert "text" in settings.validate()

    # Test caption too long
    settings.text = "Test"
    settings.caption = "a" * 201
    assert "caption" in settings.validate()

    # Test font size too large
    settings.caption = ""
    settings.font_size = 51
    assert "font_size" in settings.validate()

    # Test invalid format
    settings.font_size = 20
    settings.format = "invalid"
    assert "format" in settings.validate() 