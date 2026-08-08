import pytest
from pathlib import Path
from src.core.models import Video, Subtitle, ClipSettings, VideoScanStatus

def test_video_creation():
    video = Video(
        id="/path/to/video",
        status=VideoScanStatus.SCANNED_SUCCESS,
        width=1920,
        height=1080,
        fail_reason=None
    )
    assert video.id == "/path/to/video"
    assert video.status == VideoScanStatus.SCANNED_SUCCESS
    assert video.fail_reason == None

def test_subtitle_creation():
    sub = Subtitle(
        id="base64_encoded(/path/to/video/0)",
        start=10.0,
        end=15.0,
        text=["Test subtitle"],
        video_id="/path/to/video"
    )
    assert sub.id == "base64_encoded(/path/to/video/0)"
    assert sub.start == 10.0
    assert sub.end == 15.0
    assert sub.text[0] == "Test subtitle"
    assert sub.video_id == "/path/to/video"

def test_clip_settings_validation():
    settings = ClipSettings(
        start_time=0.0,
        end_time=5000,
        original_start_time=0.0,
        original_end_time=5.0,
        crop=False,
        resolution=500,
        video_id="/path/to/video",
        subtitle_id="base64_encoded(/path/to/video/0)",
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp",
    )
    assert settings.validate() == {}

def test_clip_settings_validation_errors():
    # Test end time before start time
    settings = ClipSettings(
        start_time=5000,
        end_time=0,
        original_start_time=5.0,
        original_end_time=0.0,
        crop=False,
        resolution=500,
        video_id="/path/to/video",
        subtitle_id="base64_encoded(/path/to/video/0)",
        font_size=20,
        caption="",
        boomerang=False,
        colour=False,
        format="webp"
    )
    assert "end" in settings.validate()

    # Test clip too long
    settings.end_time = 16000  # 16.0 - 5.0 = 11.0 seconds, which is too long
    assert "end" in settings.validate()

    # Test invalid resolution
    settings.end_time = 5.0
    settings.resolution = 10
    assert "resolution" in settings.validate()

    # Test invalid episode ID
    settings.resolution = 500
    settings.video_id = ""
    assert "video_id" in settings.validate()

    # Test font size too large
    settings.caption = ""
    settings.font_size = 51
    assert "font_size" in settings.validate()

    # Test invalid format
    settings.font_size = 20
    settings.format = "invalid"
    assert "format" in settings.validate()