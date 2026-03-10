import requests
from bs4 import BeautifulSoup
import os
import sys
import re  # ЭТО БЫЛО НУЖНО!
from datetime import datetime

VK_GROUP = os.environ.get('VK_GROUP', '236551315')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')

print("=" * 60)
print("🔍 ДИАГНОСТИКА ВК СТРАНИЦЫ")
print("=" * 60)

try:
    # Загружаем страницу
    url = f"https://vk.com/{VK_GROUP}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print(f"📥 Загрузка: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    print(f"📊 Статус: {response.status_code}")
    print(f"📦 Размер: {len(response.text)} байт")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Собираем все классы на странице
    print("\n📌 ВСЕ КЛАССЫ НА СТРАНИЦЕ:")
    classes = set()
    for tag in soup.find_all(class_=True):
        for cls in tag.get('class', []):
            classes.add(cls)
    
    # Показываем первые 50 классов
    for i, cls in enumerate(sorted(classes)[:50]):
        print(f"  {i+1}. {cls}")
    
    # Ищем посты по разным селекторам
    print("\n🔍 ПОИСК ПОСТОВ:")
    
    selectors = [
        ('div', {'class': 'post'}),
        ('div', {'class': 'wall_post'}),
        ('div', {'class': 'feed_row'}),
        ('div', {'data-post-id': True}),
    ]
    
    for name, attrs in selectors:
        found = soup.find_all(name, attrs)
        print(f"  {name} {attrs}: {len(found)}")
    
    # Проверяем ссылки на стены
    print("\n🔗 ССЫЛКИ НА СТЕНЫ:")
    wall_links = 0
    for link in soup.find_all('a', href=True):
        if 'wall' in link['href']:
            wall_links += 1
            if wall_links <= 5:
                print(f"  Найдена ссылка: {link['href']}")
    
    print(f"\n✅ Всего ссылок с 'wall': {wall_links}")
    
    # Ищем элементы с data-post-id
    print("\n🆔 ЭЛЕМЕНТЫ С data-post-id:")
    data_posts = soup.find_all(attrs={'data-post-id': True})
    print(f"  Найдено: {len(data_posts)}")
    
except Exception as e:
    print(f"❌ Ошибка: {e}")
