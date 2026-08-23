from dataclasses import dataclass
from datetime import datetime


@dataclass
class RmbPost:
    post_id: int
    nation: str
    timestamp: datetime
    message: str
    likes: int
