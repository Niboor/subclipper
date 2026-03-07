from __future__ import annotations
from dataclasses import (dataclass, field)
from pathlib import Path
from typing import Any, List, Optional, TypeVar
from enum import Enum
from sub2clip.subtitles import Subtitle as SSubtitle
from ..utils.id_encoding import (decode_id, encode_id)

class VideoScanStatus(Enum):
    UNSCANNED = 'UNSCANNED'
    SCANNING = 'SCANNING'
    SCANNED_SUCCESS = 'SCANNED_SUCCESS'
    SCANNED_FAIL = 'SCANNED_FAIL'

    @classmethod
    def _missing_(cls, value):
        return cls.UNSCANNED

@dataclass
class Video:
    id: str
    status: VideoScanStatus
    fail_reason: Optional[str]

    def already_scanned(self) -> bool:
        return self.status == VideoScanStatus.SCANNED_SUCCESS or self.status == VideoScanStatus.SCANNED_FAIL

@dataclass(order=True)
class Subtitle(SSubtitle):
    id: str = field(default="", compare=False)
    video_id: str = field(default="", compare=False)
    prv_id: str = field(default="", compare=False)
    nxt_id: str = field(default="", compare=False)

    @classmethod
    def from_subtitle(cls, subtitle: SSubtitle, id, video_id, prv_id, nxt_id) -> Subtitle:
        return cls(
            start=subtitle.start,
            end=subtitle.end,
            text=subtitle.text,
            delay=subtitle.delay,
            prv=subtitle.prv,
            nxt=subtitle.nxt,
            id=id,
            video_id=video_id,
            prv_id=prv_id,
            nxt_id=nxt_id
        )
    
    def to_sub_data(self, active: bool = False) -> dict[str, Any]:
        return {
            'id': self.id,
            'video_id': self.video_id,
            'start_time': self.start,
            'end_time': self.end,
            'original_start_time': self.start,
            'original_end_time': self.end,
            'text': self.text,
            'prv_id': self.prv_id,
            'nxt_id': self.nxt_id,
            'active': active,
        }
    
    def get_ordering(self) -> int:
        decoded_id = decode_id(self.id)
        [*_, subtitle_id] = decoded_id.split("/")
        return int(subtitle_id)

@dataclass
class ClipSettings:
    start_time: float
    end_time: float
    original_start_time: float
    original_end_time: float
    crop: bool
    resolution: int
    subtitle_id: str
    video_id: str
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
        if self.end_time - self.start_time > 10000:
            errs['end'] = 'clip too long'
        if self.resolution < 50 or self.resolution > 1024:
            errs['resolution'] = 'resolution must be between 50 and 1024'
        if self.video_id == '':
            errs['video_id'] = 'invalid video id'
        if self.font_size > 50:
            errs['font_size'] = 'font size too large'
        if self.format not in {'gif', 'webp'}:
            errs['format'] = 'invalid output format, only gif and webp are allowed'

        return errs