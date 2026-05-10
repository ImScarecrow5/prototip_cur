import asyncio
import re
import html
import feedparser
from datetime import datetime
import pytz
from typing import List
from models import NewsItem
from config import RSS_FEEDS, TIMEZONE
from mamdani import MamdaniScorer

def clean_rss_description(raw_text: str) -> str:
    if not raw_text: return ""
    t = raw_text
    t = re.sub(r'<script[^>]*>.*?</script>', '', t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r'<style[^>]*>.*?</style>', '', t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r'<img[^>]+>|<video[^>]+>|<iframe[^>]+>|<audio[^>]+>|<figure[^>]*>.*?</figure>', '', t, flags=re.IGNORECASE)
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t)
    
    # Удаляем метаданные, подписи, источники, теги
    t = re.sub(r'[\(\[\{]?\s*(?:изображение|фото|картинка|снимок|image|photo|picture|источник|source|via|credit|автор|by|читать далее|read more|подробнее|теги|tags|категория|category|опубликовано|published|дата|date)\s*[:\-\–]\s*[^\n\.\)\]\}]{0,120}[\)\]\}]?', '', t, flags=re.IGNORECASE)
    t = re.sub(r'^\s*(?:изображение|фото|image|photo|source|via|credit|источник|читать далее|read more|теги|tags)\s*[:\-\–]?\s*$', '', t, flags=re.IGNORECASE | re.MULTILINE)
    
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n\s*\n', '\n\n', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()

class NewsScraper:
    def __init__(self):
        self.scorer = MamdaniScorer()
        self.tz = pytz.timezone(TIMEZONE)

    async def collect_all_news(self) -> List[NewsItem]:
        def _parse_feed_sync(url: str) -> list:
            items = []
            try:
                feed = feedparser.parse(url)
                for e in feed.entries:
                    link = e.get('link')
                    if not link: continue
                    
                    raw = e.get('content', [{}])[0].get('value') or e.get('summary') or e.get('description', '')
                    summary = clean_rss_description(raw)
                
                    pub = e.get('published_parsed')
                    if pub:
                        try:
                            dt_naive = datetime(*pub[:6])
                            dt = pytz.UTC.localize(dt_naive).astimezone(self.tz)
                        except Exception:
                            dt = datetime.now(self.tz)
                    else:
                        dt = datetime.now(self.tz)
                        
                    items.append(NewsItem(
                        title=e.get('title', 'Без заголовка').strip(),
                        link=link, published=dt, source_url=url, summary=summary
                    ))
            except Exception as ex:
                print(f"⚠️ Ошибка парсинга {url}: {ex}")
            return items

        tasks = [asyncio.to_thread(_parse_feed_sync, u) for u in RSS_FEEDS]
        results = await asyncio.gather(*tasks)
        
        all_items, seen = [], set()
        for lst in results:
            for i in lst:
                if i.link not in seen:
                    seen.add(i.link)
                    all_items.append(i)
                    
        scored = [self.scorer.score_news(i) for i in all_items]
        scored.sort(key=lambda x: (x.is_important, x.score), reverse=True)
        # Оставляем только новости с описанием
        scored = [i for i in scored if i.summary]
        print(f"📡 Собрал {len(scored)} уникальных статей с описанием")
        return scored

    def filter_by_keywords(self, items: List[NewsItem], keywords: List[str]) -> List[NewsItem]:
        return [i for i in items if any(k.lower() in i.title.lower() for k in keywords)] if keywords else items

    def filter_by_time(self, items: List[NewsItem], days: int) -> List[NewsItem]:
        from datetime import timedelta
        
        # cutoff всегда с часовым поясом
        now = datetime.now(self.tz)
        cutoff = now - timedelta(days=days)
        
        result = []
        for item in items:
            pub = item.published
            # ️ Если дата пришла без часового пояса, добавляем его
            if pub.tzinfo is None:
                pub = self.tz.localize(pub)
                
            if pub >= cutoff:
                result.append(item)
        return result