import requests
from bs4 import BeautifulSoup
import os
import sys
from datetime import datetime

VK_GROUP = os.environ.get('VK_GROUP', 'rddmnt')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')

print("=" * 50)
print(f"🚀 ПАРСЕР ЗАПУЩЕН {datetime.now()}")
print("=" * 50)

print(f"📌 VK_GROUP: {VK_GROUP}")
print(f"📌 TG_CHANNEL: {TG_CHANNEL}")

print(f"\n📥 Загружаю https://vk.com/{VK_GROUP}...")

try:
    # Загружаем страницу
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    response = requests.get(f"https://vk.com/{VK_GROUP}", headers=headers, timeout=15)
    
    print(f"📊 Статус: {response.status_code}")
    print(f"📦 Размер: {len(response.text)} байт")
    
    # ПОКАЗЫВАЕМ ПЕРВЫЕ 2000 СИМВОЛОВ HTML
    print("\n" + "=" * 50)
    print("ПЕРВЫЕ 2000 СИМВОЛОВ СТРАНИЦЫ:")
    print("=" * 50)
    print(response.text[:2000])
    print("=" * 50)
    
    # Ищем посты
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Показываем все классы на странице
    print("\n📌 УНИКАЛЬНЫЕ КЛАССЫ НА СТРАНИЦЕ:")
    classes = set()
    for elem in soup.find_all(class_=True):
        for cls in elem.get('class', []):
            classes.add(cls)
    
    for cls in sorted(list(classes))[:50]:
        print(f"  - {cls}")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")

print("\n✅ Парсер завершил работу")
