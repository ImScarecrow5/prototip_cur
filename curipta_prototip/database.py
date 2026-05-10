import sqlite3
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Set, Dict, Optional
from models import NewsItem, UserFilter
from config import DB_PATH, SEEN_RETENTION_DAYS, MAX_RETRY


class Database:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=10000')
        conn.execute('PRAGMA synchronous=NORMAL')
        return conn
    
    def _init_db(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_connection()
        try:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id INTEGER PRIMARY KEY, username TEXT, subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS user_seen_links (
                    chat_id INTEGER, link TEXT, title TEXT, seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    score REAL DEFAULT 0.0, is_important INTEGER DEFAULT 0, PRIMARY KEY (chat_id, link)
                );
                CREATE TABLE IF NOT EXISTS user_filters (
                    chat_id INTEGER, keyword TEXT, weight REAL DEFAULT 1.0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, keyword)
                );
                CREATE INDEX IF NOT EXISTS idx_seen_chat ON user_seen_links(chat_id);
                CREATE INDEX IF NOT EXISTS idx_seen_time ON user_seen_links(seen_at);
            ''')
            # Миграция для старых БД
            for col, default in [('weight REAL DEFAULT 1.0', 'user_filters'), ('score REAL DEFAULT 0.0', 'user_seen_links'), ('is_important INTEGER DEFAULT 0', 'user_seen_links')]:
                try: conn.execute(f"ALTER TABLE {col.split()[-1]} ADD COLUMN {col.split(' ')[0]} {col.split(' ')[1]} DEFAULT {col.split(' ')[-1]}")
                except: pass
            conn.execute('DELETE FROM user_seen_links WHERE seen_at < datetime("now", ?)', (f'-{SEEN_RETENTION_DAYS} days',))
            conn.commit()
        finally:
            conn.close()

    async def _execute_with_retry(self, query_func):
        for attempt in range(MAX_RETRY):
            try:
                async with self._lock:
                    conn = self._get_connection()
                    try: return query_func(conn)
                    finally: conn.close()
            except sqlite3.OperationalError as e:
                if 'database is locked' in str(e) and attempt < MAX_RETRY - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise
        return None

    async def add_subscriber(self, chat_id: int, username: str):
        await self._execute_with_retry(lambda c: (c.execute('INSERT OR IGNORE INTO subscribers VALUES (?, ?, datetime("now"))', (chat_id, username)), c.commit())[1])
    async def remove_subscriber(self, chat_id: int):
        await self._execute_with_retry(lambda c: (c.execute('DELETE FROM subscribers WHERE chat_id = ?', (chat_id,)), c.execute('DELETE FROM user_filters WHERE chat_id = ?', (chat_id,)), c.commit())[2])
    async def get_subscribers(self) -> List[int]:
        return await self._execute_with_retry(lambda c: [r['chat_id'] for r in c.execute('SELECT chat_id FROM subscribers').fetchall()]) or []
    
    async def mark_seen(self, chat_id: int, items: List[NewsItem]):
        if not items:
            return
        
        data = [(chat_id, i.link, i.title, i.score, 1 if i.is_important else 0) for i in items]
        
        await self._execute_with_retry(lambda c: (
            c.executemany(
                'INSERT OR REPLACE INTO user_seen_links (chat_id, link, title, seen_at, score, is_important) VALUES (?, ?, ?, datetime("now"), ?, ?)',
                data
            ), 
            c.commit()
        )[1])
    async def get_seen_links(self, chat_id: int) -> Set[str]:
        return await self._execute_with_retry(lambda c: {r['link'] for r in c.execute('SELECT link FROM user_seen_links WHERE chat_id = ?', (chat_id,)).fetchall()}) or set()
    async def get_unseen_important(self, chat_id: int, days: int = 7) -> List[Dict]:
        rows = await self._execute_with_retry(lambda c: c.execute('SELECT link, title, score, seen_at FROM user_seen_links WHERE chat_id = ? AND is_important = 1 AND seen_at < datetime("now", ?) ORDER BY score DESC', (chat_id, f'-{days} days')).fetchall())
        return [dict(r) for r in rows] if rows else []

    async def add_filter(self, chat_id: int, keyword: str, weight: float = 1.0):
        await self._execute_with_retry(lambda c: (c.execute('INSERT OR REPLACE INTO user_filters VALUES (?, ?, ?, datetime("now"))', (chat_id, keyword, weight)), c.commit())[1])
    async def remove_filter(self, chat_id: int, keyword: str):
        await self._execute_with_retry(lambda c: (c.execute('DELETE FROM user_filters WHERE chat_id = ? AND keyword = ?', (chat_id, keyword)), c.commit())[1])
    async def get_filters(self, chat_id: int) -> List[UserFilter]:
        rows = await self._execute_with_retry(lambda c: c.execute('SELECT keyword, weight, created_at FROM user_filters WHERE chat_id = ?', (chat_id,)).fetchall())
        return [UserFilter(chat_id=chat_id, keyword=r['keyword'], weight=r['weight'], created_at=datetime.fromisoformat(r['created_at'])) for r in rows] if rows else []
    async def clear_filters(self, chat_id: int):
        await self._execute_with_retry(lambda c: (c.execute('DELETE FROM user_filters WHERE chat_id = ?', (chat_id,)), c.commit())[1])