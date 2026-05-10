# test.py - проверьте перед запуском
from config import API_ID, API_HASH, BOT_TOKEN

print("Проверка конфигурации:")
print(f"API_ID: {API_ID}")
print(f"  - Тип: {type(API_ID)}")
print(f"  - В диапазоне? {-2147483648 <= API_ID <= 2147483647}")
print(f"  - Длина: {len(str(API_ID))} цифр")

print(f"\nAPI_HASH: {API_HASH[:8]}...{API_HASH[-8:] if len(API_HASH) > 16 else API_HASH}")
print(f"  - Тип: {type(API_HASH)}")
print(f"  - Длина: {len(API_HASH)} символов (должно быть 32)")

print(f"\nBOT_TOKEN: {BOT_TOKEN.split(':')[0] if ':' in BOT_TOKEN else 'INVALID'}:...")
print(f"  - Тип: {type(BOT_TOKEN)}")
print(f"  - Содержит ':'? {':' in BOT_TOKEN}")

# Проверка
if not (-2147483648 <= API_ID <= 2147483647):
    print("\n❌ API_ID вне диапазона! Получите новый на my.telegram.org")
elif len(API_HASH) != 32:
    print("\n❌ API_HASH должен быть 32 символа!")
elif ':' not in BOT_TOKEN:
    print("\n❌ BOT_TOKEN должен содержать ':'!")
else:
    print("\n✅ Все параметры валидны!")