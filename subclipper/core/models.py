from dataclasses import (dataclass, field)
from pathlib import Path
from typing import List, Optional
from sub2clip.subtitles import Subtitle as SSubtitle

@dataclass
class Video:
    id: int
    title: str
    path: Path
    subs: List['Subtitle']

@dataclass(order=True)
class Subtitle(SSubtitle):
    id: int = field(default=0, compare=False)
    video_id: int = field(default=0, compare=False)

    @classmethod
    def from_subtitle(self, subtitle: SSubtitle, id, video_id) -> Subtitle:
        return self(
            start=subtitle.start,
            end=subtitle.end,
            text=subtitle.text,
            delay=subtitle.delay,
            prv=subtitle.prv,
            nxt=subtitle.nxt,
            id=id,
            video_id = video_id
        )

@dataclass
class ClipSettings:
    start_time: float
    end_time: float
    original_start_time: float
    original_end_time: float
    crop: bool
    resolution: int
    id: int
    episode: int
    font_size: int
    caption: str
    boomerang: bool
    colour: bool
    format: str

    def validate(self) -> dict:
        """Validate the clip settings and return any errors."""
        errs = {}

        if self.end_time <= self.start_time:
            errs['end'] = 'end time must be after start time'
        if self.end_time - self.start_time > 10:
            errs['end'] = 'clip too long'
        if self.resolution < 50 or self.resolution > 1024:
            errs['resolution'] = 'resolution must be between 50 and 1024'
        if self.episode < 0:
            errs['episode'] = 'invalid episode id'
        if len(self.caption) > 200:
            errs['caption'] = 'caption too large'
        if self.font_size > 50:
            errs['font_size'] = 'font size too large'
        if self.format not in {'gif', 'webp'}:
            errs['format'] = 'invalid output format, only gif and webp are allowed'

        return errs