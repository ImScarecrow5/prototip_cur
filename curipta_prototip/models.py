from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class NewsItem:
    title: str
    link: str
    published: datetime
    source_url: str
    summary: str = ""
    score: float = 0.0
    is_important: bool = False
    s1_score: float = 0.0
    s2_score: float = 0.0
    s3_score: float = 0.0
    
    def __hash__(self): return hash(self.link)
    def __eq__(self, other): return isinstance(other, NewsItem) and self.link == other.link

@dataclass
class UserFilter:
    chat_id: int
    keyword: str
    weight: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)