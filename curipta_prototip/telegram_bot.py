import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
import pytz
from models import NewsItem, UserFilter
from database import Database
from news_scraper import NewsScraper
from config import API_ID, API_HASH, BOT_TOKEN, NEWS_INTERVAL_MINUTES, TIMEZONE
from mamdani import MamdaniScorer
from telethon import TelegramClient, events
from telethon.sessions import MemorySession
from telethon.tl.types import ReplyInlineMarkup, KeyboardButtonCallback

class TelegramBot:
    def __init__(self):
        self.db = Database()
        self.scraper = NewsScraper()
        self.scorer = MamdaniScorer()
        self.tz = pytz.timezone(TIMEZONE)
        self.user_state: Dict[int, dict] = {}
    
    async def start(self):
        self.client = TelegramClient(MemorySession(), API_ID, API_HASH)
        await self.client.start(bot_token=BOT_TOKEN)
        print(f"🤖 Бот запущен: @{(await self.client.get_me()).username}")
        
        self.client.add_event_handler(self.handle_message, events.NewMessage)
        self.client.add_event_handler(self.handle_callback, events.CallbackQuery)
        
        await asyncio.gather(self.client.run_until_disconnected(), self.broadcast_loop())

    async def handle_callback(self, event):
        try:
            chat_id = event.chat_id
            data = event.data.decode('utf-8')
            if chat_id not in self.user_state:
                await event.answer("Сессия истекла. Отправьте /news заново", alert=True); return
            
            state = self.user_state[chat_id]
            idx = state['index']
            if data == 'next' and idx < len(state['items']) - 1: state['index'] = idx + 1
            elif data == 'prev' and idx > 0: state['index'] = idx - 1
            elif data == 'first': state['index'] = 0
            elif data == 'last': state['index'] = len(state['items']) - 1
            elif data == 'noop': await event.answer(); return
            else: await event.answer(); return
            
            await self.show_single_news(chat_id, state['items'], state['index'], state['days'], state['message_id'])
            await event.answer()
        except Exception as e:
            print(f"💥 Callback error: {e}"); await event.answer("Ошибка", alert=True)

    async def show_single_news(self, chat_id: int, items: List[NewsItem], index: int, days: int, message_id: int = None) -> int:
        if not items or index < 0 or index >= len(items): return message_id
        item = items[index]
        
        important = "🔥 **ВАЖНО**\n\n" if item.is_important else ""
        text = f"{important}{item.title}\n\n{item.summary}\n\n🔗 [Открыть новость]({item.link})"
        
        buttons = [[
            KeyboardButtonCallback('⏮ Начало', b'first'),
            KeyboardButtonCallback('◀️ Назад', b'prev') if index > 0 else KeyboardButtonCallback('⏸️', b'noop'),
            KeyboardButtonCallback('Вперёд ▶️', b'next') if index < len(items) - 1 else KeyboardButtonCallback('⏸️', b'noop'),
            KeyboardButtonCallback('Конец ⏭️', b'last')
        ]]
        footer = f"\n📊 {index + 1} из {len(items)} (за {days} дн.)"
        full = text + footer
        
        try:
            if len(full) > 4000:
                chunks = [full[i:i+4000] for i in range(0, len(full), 4000)]
                for i, ch in enumerate(chunks):
                    is_last = i == len(chunks) - 1
                    if message_id and i == 0:
                        await self.client.edit_message(chat_id, message_id, ch, parse_mode='markdown', link_preview=False, buttons=buttons if is_last else None)
                    else:
                        m = await self.client.send_message(chat_id, ch, parse_mode='markdown', link_preview=False, buttons=buttons if is_last else None)
                        if i == 0 and not message_id: message_id = m.id
            else:
                if message_id:
                    await self.client.edit_message(chat_id, message_id, full, parse_mode='markdown', link_preview=False, buttons=buttons)
                else:
                    m = await self.client.send_message(chat_id, full, parse_mode='markdown', link_preview=False, buttons=buttons)
                    message_id = m.id
        except Exception as e:
            print(f"⚠️ Send/Edit error: {e}")
        return message_id

    async def handle_message(self, event):
        try:
            # Пропускаем сообщения из групп/каналов или от других ботов
            if not event.is_private or (event.sender and event.sender.bot):
                return

            chat_id = event.chat_id
            text = event.message.text.strip() if event.message.text else ''
            
            # --- ОБРАБОТКА КОМАНД ---

            # 1. Старт
            if text.lower() in ['/start', '/subscribe']:
                await self.db.add_subscriber(chat_id, event.sender.username or event.sender.first_name or "User")
                await event.respond(
                    "🎉 Добро пожаловать!\n\n"
                    "📌 Команды:\n"
                    "/news — читать новости\n"
                    "/time <дней> — новости за N дней\n"
                    "/filter add <слово> — добавить фильтр\n"
                    "/filter list — список фильтров\n"
                    "/filter remove <слово> — удалить фильтр\n"
                    "/stop — отписаться",
                    parse_mode='markdown'
                )

            # 2. Новости
            elif text.lower() == '/news':
                await self.send_news_interactive(chat_id, days=7)

            # 3. Новости за период
            elif text.lower().startswith('/time'):
                parts = text.split()
                days = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 7
                await self.send_news_interactive(chat_id, days=days)

            # 4. Добавить фильтр
            elif text.lower().startswith('/filter add'):
                parts = text.split(maxsplit=2)
                if len(parts) >= 3:
                    keyword = parts[2]
                    await self.db.add_filter(chat_id, keyword)
                    await event.respond(f"✅ Фильтр `{keyword}` добавлен.", parse_mode='markdown')
                else:
                    await event.respond("❌ Использование: `/filter add <слово>`", parse_mode='markdown')

            # 5. СПИСОК ФИЛЬТРОВ (Новое)
            elif text.lower() == '/filter list':
                filters = await self.db.get_filters(chat_id)
                if not filters:
                    await event.respond(" У вас нет активных фильтров.")
                else:
                    msg = "🔍 **Ваши активные фильтры:**\n\n"
                    for f in filters:
                        msg += f"• `{f.keyword}`\n"
                    msg += "\nЧтобы удалить: `/filter remove <слово>`"
                    await event.respond(msg, parse_mode='markdown')

            # 6. УДАЛИТЬ ФИЛЬТР (Новое)
            elif text.lower().startswith('/filter remove'):
                parts = text.split(maxsplit=2)
                if len(parts) >= 3:
                    keyword = parts[2]
                    await self.db.remove_filter(chat_id, keyword)
                    await event.respond(f"✅ Фильтр `{keyword}` удален.", parse_mode='markdown')
                else:
                    await event.respond("❌ Использование: `/filter remove <слово>`", parse_mode='markdown')

            # 7. Стоп
            elif text.lower() in ['/stop', '/unsubscribe']:
                await self.db.remove_subscriber(chat_id)
                self.user_state.pop(chat_id, None)
                await event.respond(" Вы отписались.")

            else:
                # Если команда не распознана, можно ничего не делать или ответить
                pass

        except Exception as e:
            print(f"💥 Ошибка в handle_message: {e}")
            try:
                await event.respond(f"❌ Произошла ошибка: {e}")
            except:
                pass
    async def send_news_interactive(self, chat_id: int, days: int = 7):
        try:
            filters = await self.db.get_filters(chat_id)
            kws = [f.keyword for f in filters]
            news = await self.scraper.collect_all_news()
            if kws: news = self.scraper.filter_by_keywords(news, kws)
            news = self.scraper.filter_by_time(news, days)
            if not news:
                await self.client.send_message(chat_id, f"ℹ️ Новостей за {days} дней нет."); return
            
            seen = await self.db.get_seen_links(chat_id)
            unseen = [i for i in news if i.link not in seen]
            if not unseen:
                old = await self.db.get_unseen_important(chat_id, days)
                await self.client.send_message(chat_id, "ℹ️ Новых нет, но есть важные из архива." if old else "ℹ️ Новых новостей нет")
                return
            
            msg_id = await self.show_single_news(chat_id, unseen, 0, days)
            self.user_state[chat_id] = {'items': unseen, 'index': 0, 'days': days, 'message_id': msg_id}
            await self.db.mark_seen(chat_id, unseen)
        except Exception as e:
            print(f"💥 Interactive error: {e}")

    async def broadcast_loop(self):
        print(f" Рассылка запущена (каждые {NEWS_INTERVAL_MINUTES} мин)")
        while True:
            await asyncio.sleep(NEWS_INTERVAL_MINUTES * 60)
            subs = await self.db.get_subscribers()
            if not subs: continue
            for cid in subs:
                try:
                    await self.send_news_interactive(cid, days=1)
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"❌ Broadcast {cid}: {e}")