#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
НовостиПро Scraper v2.0 - Safe Startup
"""

import sys
import asyncio
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('newspro')

try:
    from telethon import TelegramClient, events
    from telethon.sessions import MemorySession
    from telethon.errors import FloodWaitError
except ImportError as e:
    logger.error(f"❌ Отсутствует зависимость: {e}")
    sys.exit(1)

from telegram_bot import TelegramBot
from config import BOT_TOKEN, API_ID, API_HASH

async def safe_start(bot: TelegramBot, max_retries: int = 3):
    """Безопасный запуск с обработкой FloodWait"""
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"🔑 Попытка авторизации {attempt}/{max_retries}...")
            await bot.client.start(bot_token=BOT_TOKEN)
            logger.info("✅ Авторизация успешна")
            return True
        except FloodWaitError as e:
            logger.warning(f"⏳ Telegram требует подождать {e.seconds} сек. Ждём...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f" Ошибка авторизации: {type(e).__name__}: {e}")
            if attempt == max_retries: return False
            await asyncio.sleep(5)
    return False

async def main():
    bot = TelegramBot()
    
    # ✅ ВАЖНО: Инициализируем клиент ДО вызова safe_start
    bot.client = TelegramClient(MemorySession(), API_ID, API_HASH)
    
    # Запускаем безопасную авторизацию
    if not await safe_start(bot):
        logger.error("🚫 Не удалось авторизоваться. Запуск отменён.")
        return

    # Подключаем обработчики событий
    bot.client.add_event_handler(bot.handle_message, events.NewMessage)
    bot.client.add_event_handler(bot.handle_callback, events.CallbackQuery)
    
    # Запускаем цикл бота и фоновую рассылку
    try:
        await asyncio.gather(
            bot.client.run_until_disconnected(),
            bot.broadcast_loop()
        )
    except asyncio.CancelledError:
        logger.info("🛑 Бот остановлен")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Завершено пользователем")
    except Exception as e:
        logger.error(f"💥 Фатальная ошибка: {e}")
        sys.exit(1)