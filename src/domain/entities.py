from dataclasses import dataclass, field
import time
from typing import Dict, Any, List


@dataclass
class TriggerPacket:
    """
    Domain entity for a pipeline-triggered video clip.
    """
    clip_id: int
    video_path: str
    event_time: float
    is_ace: bool = False
    status: str = "QUEUED"
    progress: float = 0.0
    error_message: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "video_path": self.video_path,
            "event_time": self.event_time,
            "is_ace": self.is_ace,
            "status": self.status,
            "progress": self.progress,
            "error_message": self.error_message
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriggerPacket":
        return cls(
            clip_id=data["clip_id"],
            video_path=data.get("video_path", ""),
            event_time=data["event_time"],
            is_ace=data.get("is_ace", False),
            status=data.get("status", "QUEUED"),
            progress=data.get("progress", 0.0),
            error_message=data.get("error_message", "")
        )


@dataclass
class PipelineSummary:
    total: int = 0
    completed: int = 0
    failed: int = 0
    packets: List[Dict[str, Any]] = field(default_factory=list)
