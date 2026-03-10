import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import time
import re
from datetime import datetime

# ============================================
# НАСТРОЙКИ
# ============================================
VK_GROUP = os.environ.get('VK_GROUP', 'rddmnt')
TG_TOKEN = os.environ.get('TG_TOKEN', '')
TG_CHANNEL = os.environ.get('TG_CHANNEL', '-1003761499584')

class VKParser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.state_file = 'state.json'
        
    def log(self, msg):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def get_posts(self):
        """Парсит посты из ВК"""
        self.log(f"Загрузка https://vk.com/{VK_GROUP}")
        
        try:
            response = self.session.get(f"https://vk.com/{VK_GROUP}", timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Сохраняем для отладки
            with open('debug.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            self.log("✅ debug.html сохранен")
            
            posts = []
            # Ищем посты
            for post in soup.find_all('div', class_='post'):
                try:
                    # ID поста
                    link = post.find('a', class_='post_link')
                    if not link:
                        continue
                    
                    post_id = link.get('href', '').split('wall')[-1]
                    
                    # Текст
                    text = post.find('div', class_='wall_post_text')
                    text = text.text if text else ''
                    
                    # Фото
                    photos = []
                    for img in post.find_all('img'):
                        if img.get('src'):
                            photos.append(img['src'])
                    
                    posts.append({
                        'id': post_id,
                        'text': text,
                        'photos': photos[:10]
                    })
                    self.log(f"✅ Найден пост {post_id}")
                except:
                    continue
            
            self.log(f"📦 Всего постов: {len(posts)}")
            return posts
            
        except Exception as e:
            self.log(f"❌ Ошибка: {e}")
            return []
    
    def send_to_tg(self, post):
        """Отправляет в Telegram"""
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        data = {
            'chat_id': TG_CHANNEL,
            'text': f"{post['text']}\n\n{post['id']}"
        }
        return requests.post(url, json=data).ok
    
    def catchup(self):
        """Догон постов"""
        self.log("=" * 40)
        posts = self.get_posts()
        
        if not posts:
            self.log("❌ Посты не найдены")
            return
        
        for post in posts[:5]:
            if self.send_to_tg(post):
                self.log(f"✅ Отправлен {post['id']}")
            time.sleep(1)

def main():
    parser = VKParser()
    parser.log("🚀 Парсер запущен")
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if 'catchup' in cmd:
            parser.catchup()

if __name__ == "__main__":
    main()
