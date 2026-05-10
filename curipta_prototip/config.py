from pathlib import Path
import os
import logging

logger = logging.getLogger(__name__)

DATA_FOLDER = Path(os.getenv('DATA_FOLDER', './data'))
DB_PATH = DATA_FOLDER / 'newspro_bot.db'
FEEDS_FILE = Path(__file__).parent / 'feeds.txt'

DEFAULT_FEEDS = [
    'https://feeds.bbci.co.uk/news/rss.xml',
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://feeds.bbci.co.uk/news/business/rss.xml',
    'https://feeds.bbci.co.uk/news/technology/rss.xml',
]

API_ID = int(os.getenv('API_ID', 32252827))
API_HASH = os.getenv('API_HASH', '38392fdd1bbc8e4773c217c872669693')
BOT_TOKEN = os.getenv('BOT_TOKEN', '8439145567:AAE8i_QhhfmOFe9fCRrEZw-BL6nNnMTJOUo')

NEWS_INTERVAL_MINUTES = int(os.getenv('NEWS_INTERVAL_MINUTES', 30))
SEEN_RETENTION_DAYS = int(os.getenv('SEEN_RETENTION_DAYS', 30))
MAX_RETRY = 5

TRIGGERS = ['новинка', 'релиз', 'анонс', 'характеристики', 'EOL', 'новый', 'представлен', 'выпущен']
WEIGHTS = {'S1': 50, 'S2': 35, 'S3': 15}
SOURCE_SCORES = {'vendor': 15, 'media': 10, 'blog': 5}
TIMEZONE = 'Europe/Moscow'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; NewsProScraper/2.0)'}

def load_feeds() -> list[str]:
    if not FEEDS_FILE.exists():
        logger.warning(f"{FEEDS_FILE} не найден, создаю шаблон")
        FEEDS_FILE.parent.mkdir(parents=True, exist_ok=True)
        FEEDS_FILE.write_text("# RSS-источники новостей (один URL на строку)\n# Комментарии начинаются с #\n\n" + "\n".join(DEFAULT_FEEDS) + "\n")
        return DEFAULT_FEEDS.copy()
    
    feeds = []
    try:
        with open(FEEDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    feeds.append(line)
    except Exception as e:
        logger.error(f"Ошибка чтения {FEEDS_FILE}: {e}")
        return DEFAULT_FEEDS.copy()
        
    return feeds if feeds else DEFAULT_FEEDS.copy()

RSS_FEEDS = load_feeds()