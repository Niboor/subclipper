from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class Video:
    id: int
    title: str
    path: Path
    subs: List['Subtitle']

@dataclass
class Subtitle:
    id: int
    start: float
    end: float
    text: str
    video_id: int

@dataclass
class ClipSettings:
    start_time: float
    end_time: float
    original_start_time: float
    original_end_time: float
    text: str
    crop: bool
    resolution: int
    episode_id: int
    font_size: int
    caption: str
    boomerang: bool
    colour: bool
    format: str
    font_path: Path

    def validate(self) -> dict:
        """Validate the clip settings and return any errors."""
        errs = {}
        
        if self.end_time <= self.start_time:
            errs['end'] = 'end time must be after start time'
        if self.end_time - self.start_time > 10:
            errs['end'] = 'clip too long'
        if self.resolution < 50 or self.resolution > 1024:
            errs['resolution'] = 'resolution must be between 50 and 1024'
        if self.episode_id < 0:
            errs['episode'] = 'invalid episode id'
        if len(self.text) > 200:
            errs['text'] = 'subtitle text too large'
        if len(self.caption) > 200:
            errs['caption'] = 'caption too large'
        if self.font_size > 50:
            errs['font_size'] = 'font size too large'
        if self.format not in {'gif', 'webp'}:
            errs['format'] = 'invalid output format, only gif and webp are allowed'
            
        return errs 